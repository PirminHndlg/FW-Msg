import json

from django.conf import settings
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from Global.models import CustomUser, PersonCluster
from ORG.models import Organisation
from seminar.views import parse_seminar_key


class ParseSeminarKeyTests(TestCase):
    def test_bewertungen_cookie(self):
        self.assertEqual(
            parse_seminar_key('f31r3u10'),
            ('bewertungen', {'freiwilliger': '31', 'einheit': '3', 'bewerter': '10'}),
        )

    def test_bewertung_field(self):
        self.assertEqual(
            parse_seminar_key('f31q7r3u10'),
            ('bewertung', {'freiwilliger': '31', 'frage': '7', 'einheit': '3', 'bewerter': '10'}),
        )

    def test_comment_with_and_without_category(self):
        self.assertEqual(
            parse_seminar_key('comment31r3u10c5n1'),
            ('comment', {'freiwilliger': '31', 'einheit': '3', 'bewerter': '10', 'category': '5', 'name': True}),
        )
        self.assertEqual(
            parse_seminar_key('comment31r3u10n0'),
            ('comment', {'freiwilliger': '31', 'einheit': '3', 'bewerter': '10', 'name': False}),
        )

    def test_other_names(self):
        for key in ['firstVisit', 'selectedPersonCluster_F', 'fbroken', 'commentx', 'csrftoken', '']:
            self.assertEqual(parse_seminar_key(key), (None, None), key)


class SeminarSaveTests(TestCase):
    """Speichern über refresh (Cookies), sync (localStorage) und evaluate_post (Formular)"""

    def setUp(self):
        from BW.models import Bewerber
        from seminar.models import Einheit, Frage, Fragekategorie, Seminar

        self.org = Organisation.objects.create(name='Test Org', email='test@test.com')
        team_cluster = PersonCluster.objects.create(org=self.org, name='Team', view='T')
        bw_cluster = PersonCluster.objects.create(org=self.org, name='BW', view='B')
        self.user = User.objects.create_user(username='team', password='pass12345')
        CustomUser.objects.create(org=self.org, user=self.user, person_cluster=team_cluster)
        bw_user = User.objects.create_user(username='bewerber')
        CustomUser.objects.create(org=self.org, user=bw_user, person_cluster=bw_cluster)
        self.bewerber, _ = Bewerber.objects.get_or_create(org=self.org, user=bw_user)

        seminar = Seminar.objects.create(org=self.org, name='Seminar')
        seminar.verschwiegenheit_von_user.add(self.user)
        seminar.bewerber.add(self.bewerber)
        self.einheit = Einheit.objects.create(org=self.org, name='Einheit')
        self.kategorie = Fragekategorie.objects.create(org=self.org, name='Kategorie')
        self.frage = Frage.objects.create(org=self.org, text='Frage', kategorie=self.kategorie)
        self.client.login(username='team', password='pass12345')

    def test_refresh_ignores_other_cookies_starting_with_f(self):
        from seminar.models import Bewertung, Kommentar

        b, e, u = self.bewerber.id, self.einheit.id, self.user.id
        session = f'{settings.SESSION_COOKIE_NAME}={self.client.cookies[settings.SESSION_COOKIE_NAME].value}'
        cookies = '; '.join([
            session,
            'firstVisit=1790842493736',
            'selectedPersonCluster_F=12',
            f'f{b}r{e}u{u}={{"{self.frage.id}":"4"}}',
            f'comment{b}r{e}u{u}c{self.kategorie.id}n1=Gute Idee',
        ])
        response = self.client.get(reverse('refresh'), HTTP_COOKIE=cookies)

        self.assertRedirects(response, reverse('seminar_home'), fetch_redirect_response=False)
        bewertung = Bewertung.objects.get(bewerber=self.bewerber, einheit=self.einheit, bewerter=self.user)
        self.assertEqual(bewertung.bewertung, 4)
        kommentar = Kommentar.objects.get(bewerber=self.bewerber, einheit=self.einheit, bewerter=self.user)
        self.assertEqual(kommentar.kategorie, self.kategorie)
        self.assertTrue(kommentar.show_name_at_presentation)
        self.assertNotIn('firstVisit', response.cookies)

    def test_evaluate_post_saves_fields_of_current_user(self):
        from seminar.models import Bewertung, Kommentar

        b, e, u = self.bewerber.id, self.einheit.id, self.user.id
        response = self.client.post(reverse('evaluate-post'), {
            f'f{b}q{self.frage.id}r{e}u{u}': '3',
            f'f{b}q{self.frage.id}r{e}u{u + 1}': '1',  # andere:r Bewerter:in
            f'comment{b}r{e}u{u}n0': 'Allgemein',
            'firstVisit': '1',
        })

        self.assertRedirects(response, reverse('seminar_home'), fetch_redirect_response=False)
        bewertung = Bewertung.objects.get(bewerber=self.bewerber, einheit=self.einheit)
        self.assertEqual((bewertung.bewerter, bewertung.bewertung), (self.user, 3))
        kommentar = Kommentar.objects.get(bewerber=self.bewerber, einheit=self.einheit, bewerter=self.user)
        self.assertIsNone(kommentar.kategorie)
        self.assertFalse(kommentar.show_name_at_presentation)

    def _sync(self, entries, manual=False):
        return self.client.post(
            reverse('seminar_sync'),
            data=json.dumps({'entries': entries, 'manual': manual}),
            content_type='application/json',
        )

    def test_sync_saves_entries_and_returns_them(self):
        from seminar.models import Bewertung, Kommentar

        b, e, u = self.bewerber.id, self.einheit.id, self.user.id
        entries = {
            f'f{b}r{e}u{u}': json.dumps({str(self.frage.id): '2'}),
            f'comment{b}r{e}u{u}n1': 'Kommentar mit ; und = und Ümläuten',
        }
        response = self._sync(entries)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['saved'], entries)
        self.assertEqual(response.json()['inserted'], 2)
        self.assertEqual(Bewertung.objects.get(bewerber=self.bewerber).bewertung, 2)
        self.assertEqual(
            Kommentar.objects.get(bewerber=self.bewerber, kategorie__isnull=True).text,
            'Kommentar mit ; und = und Ümläuten',
        )

        # Erneutes Senden (z.B. Antwort ging verloren) ist unkritisch
        response = self._sync({f'f{b}r{e}u{u}': json.dumps({str(self.frage.id): '5'})})
        self.assertEqual(response.json()['edited'], 1)
        self.assertEqual(Bewertung.objects.get(bewerber=self.bewerber).bewertung, 5)

    def test_sync_keeps_entries_it_cannot_save(self):
        b, e, u = self.bewerber.id, self.einheit.id, self.user.id
        response = self._sync({
            f'f{b}r{e}u{u + 1}': json.dumps({str(self.frage.id): '1'}),  # andere:r Bewerter:in
            f'f{b}r{e}u{u}': json.dumps({'999999': '1'}),                 # unbekannte Frage
            'firstVisit': '1',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['saved'], {})

    def test_sync_ignores_empty_new_comment(self):
        from seminar.models import Kommentar

        b, e, u = self.bewerber.id, self.einheit.id, self.user.id
        response = self._sync({f'comment{b}r{e}u{u}n1': ''})
        self.assertIn(f'comment{b}r{e}u{u}n1', response.json()['saved'])
        self.assertFalse(Kommentar.objects.exists())

    def test_sync_manual_adds_message(self):
        response = self._sync({}, manual=True)
        self.assertEqual(response.status_code, 200)
        home = self.client.get(reverse('seminar_home'))
        self.assertContains(home, 'Erfolgreich bewertet, 0 Bewertungen hinzugefügt, 0 bearbeitet')

    def test_sync_rejects_get_and_invalid_body(self):
        self.assertEqual(self.client.get(reverse('seminar_sync')).status_code, 405)
        response = self.client.post(reverse('seminar_sync'), data='kein json', content_type='application/json')
        self.assertEqual(response.status_code, 400)
