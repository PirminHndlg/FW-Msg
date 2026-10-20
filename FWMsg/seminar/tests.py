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


class UnsavedCookieHintTests(TestCase):
    """Hinweis auf der Seminar-Startseite, wenn Bewertungen/Kommentare nur in Cookies liegen"""

    def setUp(self):
        self.org = Organisation.objects.create(name='Test Org', email='test@test.com')
        cluster = PersonCluster.objects.create(org=self.org, name='Team', view='T')
        self.user = User.objects.create_user(username='team', password='pass12345')
        CustomUser.objects.create(org=self.org, user=self.user, person_cluster=cluster)
        self.client.login(username='team', password='pass12345')

    def _get_home(self, cookie_header=''):
        # Roh wie vom Browser gesetzt (evaluate.js schreibt JSON unverändert in den Cookie);
        # der Header ersetzt die Client-Cookies, daher die Session mitschicken
        session = f'{settings.SESSION_COOKIE_NAME}={self.client.cookies[settings.SESSION_COOKIE_NAME].value}'
        return self.client.get(reverse('seminar_home'), HTTP_COOKIE='; '.join(filter(None, [session, cookie_header])))

    def test_no_unsaved_entries(self):
        response = self._get_home()
        self.assertEqual(response.context['unsaved_count'], 0)
        self.assertNotContains(response, 'noch nicht gespeichert')

    def test_counts_ratings_and_comments_of_current_user(self):
        uid = self.user.id
        cookies = '; '.join([
            f'f12r3u{uid}={{"7":"3","8":"4"}}',      # 2 Bewertungen
            f'comment12r3u{uid}c5n1=Gute Idee',      # Kommentar mit Kategorie
            f'comment12r3u{uid}n0=Allgemein',        # Kommentar ohne Kategorie
            f'f12r3u{uid + 1}={{"7":"1"}}',          # andere:r Bewerter:in
        ])
        response = self._get_home(cookies)
        self.assertEqual(response.context['unsaved_count'], 4)
        self.assertContains(response, '4 Einträge sind noch nicht gespeichert')

    def test_ignores_malformed_cookies(self):
        response = self._get_home('foo=bar; fbroken=1; commentx=1')
        self.assertEqual(response.context['unsaved_count'], 0)


class RefreshCookieTests(TestCase):
    """refresh speichert die Bewertungs-/Kommentar-Cookies und ignoriert fremde Cookies"""

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
