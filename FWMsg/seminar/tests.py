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


class PresentationAttributesTests(TestCase):
    """Auswahl der Steckbrief-Felder in der Auswertung (powerPoint.html)"""

    def setUp(self):
        from BW.models import Bewerber
        from Global.models import Attribute, UserAttribute
        from seminar.models import Seminar

        self.org = Organisation.objects.create(name='Test Org', email='test@test.com')
        org_cluster = PersonCluster.objects.create(org=self.org, name='Org', view='O')
        bw_cluster = PersonCluster.objects.create(org=self.org, name='BW', view='B')
        self.bw_cluster = bw_cluster
        fw_cluster = PersonCluster.objects.create(org=self.org, name='FW', view='F')
        inactive_bw_cluster = PersonCluster.objects.create(org=self.org, name='BW alt', view='B', active=False)
        admin = User.objects.create_user(username='admin', password='pass12345')
        CustomUser.objects.create(org=self.org, user=admin, person_cluster=org_cluster)
        bw_user = User.objects.create_user(username='bewerber', first_name='Anna', last_name='Muster')
        CustomUser.objects.create(org=self.org, user=bw_user, person_cluster=bw_cluster)
        self.bewerber, _ = Bewerber.objects.get_or_create(org=self.org, user=bw_user)

        self.seminar = Seminar.objects.create(org=self.org, name='Seminar')
        self.seminar.bewerber.add(self.bewerber)

        self.alter = Attribute.objects.create(org=self.org, name='Alter')
        self.alter.person_cluster.add(bw_cluster)
        self.wohnort = Attribute.objects.create(org=self.org, name='Wohnort')
        self.wohnort.person_cluster.add(bw_cluster)
        self.fw_only = Attribute.objects.create(org=self.org, name='Nur FW')
        self.fw_only.person_cluster.add(fw_cluster)
        self.inactive_only = Attribute.objects.create(org=self.org, name='Nur alte BW')
        self.inactive_only.person_cluster.add(inactive_bw_cluster)
        UserAttribute.objects.create(org=self.org, user=bw_user, attribute=self.alter, value='21')
        UserAttribute.objects.create(org=self.org, user=bw_user, attribute=self.wohnort, value='Berlin')

        self.client.login(username='admin', password='pass12345')

    def test_no_fields_shown_without_selection(self):
        response = self.client.get(reverse('evaluate_all'))
        self.assertEqual(response.context['user_attributes'], [])
        self.assertEqual(
            list(response.context['selectable_attributes']), [self.alter, self.wohnort]
        )

    def test_save_selection_and_show_selected_fields(self):
        response = self.client.post(reverse('save_presentation_attributes'), {
            'fid': self.bewerber.id,
            'attributes': [self.wohnort.id, self.fw_only.id, self.inactive_only.id],
        })
        self.assertRedirects(
            response, reverse('evaluate_all') + f'?fid={self.bewerber.id}', fetch_redirect_response=False
        )
        # Fields outside the active Bewerber clusters are ignored
        self.assertEqual(list(self.seminar.presentation_attributes.all()), [self.wohnort])

        response = self.client.get(response.url)
        self.assertEqual(response.context['user_attributes'], [{'name': 'Wohnort', 'type': 'T', 'value': 'Berlin'}])

    def test_no_fields_shown_for_inactive_cluster(self):
        self.seminar.presentation_attributes.set([self.alter, self.wohnort])
        self.bw_cluster.active = False
        self.bw_cluster.save()

        response = self.client.get(reverse('evaluate_all') + f'?fid={self.bewerber.id}')
        self.assertEqual(response.context['user_attributes'], [])

    def test_boolean_fields_shown_as_icons(self):
        from Global.models import Attribute, UserAttribute

        ja = Attribute.objects.create(org=self.org, name='Führerschein', type='B')
        nein = Attribute.objects.create(org=self.org, name='Vegetarisch', type='B')
        for attribute in (ja, nein):
            attribute.person_cluster.add(self.bw_cluster)
        UserAttribute.objects.create(org=self.org, user=self.bewerber.user, attribute=ja, value='True')
        UserAttribute.objects.create(org=self.org, user=self.bewerber.user, attribute=nein, value='False')
        self.seminar.presentation_attributes.set([ja, nein])

        response = self.client.get(reverse('evaluate_all') + f'?fid={self.bewerber.id}')
        self.assertContains(response, 'bi-check-lg text-success', count=1)
        self.assertContains(response, 'bi-x-lg text-danger', count=1)
        self.assertNotContains(response, '>True<')

    def test_save_requires_post(self):
        response = self.client.get(reverse('save_presentation_attributes'))
        self.assertEqual(response.status_code, 405)


class AssignViewTests(TestCase):
    """Zuteilungsseite: Gruppierung, Zähler und konstante Anzahl an Queries"""

    def setUp(self):
        from Global.models import Einsatzland2, Einsatzstelle2
        from seminar.models import Seminar

        self.org = Organisation.objects.create(name='Test Org', email='test@test.com')
        org_cluster = PersonCluster.objects.create(org=self.org, name='Org', view='O')
        self.bw_cluster = PersonCluster.objects.create(org=self.org, name='BW', view='B')
        admin = User.objects.create_user(username='admin', password='pass12345')
        CustomUser.objects.create(org=self.org, user=admin, person_cluster=org_cluster)
        self.seminar = Seminar.objects.create(org=self.org, name='Seminar')

        self.land = Einsatzland2.objects.create(org=self.org, name='Land A', code='de')
        self.stelle_a = Einsatzstelle2.objects.create(org=self.org, name='A', land=self.land, max_freiwillige=2)
        self.stelle_b = Einsatzstelle2.objects.create(org=self.org, name='B', land=self.land, max_freiwillige=3)
        self.client.login(username='admin', password='pass12345')

    def _create_bewerber(self, name, endbewertung=None, note=None, zuteilung=None, wish=None):
        from BW.models import Bewerber

        user = User.objects.create_user(username=name, first_name=name, last_name='X')
        CustomUser.objects.create(org=self.org, user=user, person_cluster=self.bw_cluster)
        bewerber, _ = Bewerber.objects.get_or_create(org=self.org, user=user)
        bewerber.endbewertung = endbewertung
        bewerber.note = note
        bewerber.zuteilung = zuteilung
        bewerber.first_wish_einsatzstelle = wish
        bewerber.save()
        self.seminar.bewerber.add(bewerber)
        return bewerber

    def test_grouping_order_and_counters(self):
        n = self._create_bewerber('n', 'N', 1.0, self.stelle_a, wish=self.stelle_b)
        g2 = self._create_bewerber('g2', 'G', 2.0, self.stelle_a)
        g1 = self._create_bewerber('g1', 'G', 1.5, self.stelle_a)
        offen = self._create_bewerber('offen', 'B', 1.0, wish=self.stelle_a)

        response = self.client.get(reverse('assign'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['freiwillige_ohne_zuteilung'], [offen])
        self.assertEqual(response.context['freiwillige_mit_zuteilung'], [g1, g2, n])

        land = response.context['laender'][0]
        self.assertEqual([(s.name, fw) for s, fw in land['stellen']], [('A', [g1, g2, n]), ('B', [])])
        self.assertEqual((land['current_fw'], land['max_fw']), (3, 5))
        self.assertContains(response, '3/5')

    def test_query_count_independent_of_data_size(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        from Global.models import Einsatzland2, Einsatzstelle2

        self._create_bewerber('first', 'G', 1.0, self.stelle_a, wish=self.stelle_b)
        self.client.get(reverse('assign'))  # warm-up (identifiers, sessions)
        with CaptureQueriesContext(connection) as small:
            self.client.get(reverse('assign'))

        for i in range(3):
            land = Einsatzland2.objects.create(org=self.org, name=f'Land {i}', code='fr')
            stelle = Einsatzstelle2.objects.create(org=self.org, name=f'S{i}', land=land, max_freiwillige=1)
            self._create_bewerber(f'bw{i}', 'B', 2.0, stelle, wish=self.stelle_a)
            self._create_bewerber(f'open{i}', None, None, wish=stelle)
        self.client.get(reverse('assign'))  # warm-up for new users
        with CaptureQueriesContext(connection) as large:
            self.client.get(reverse('assign'))

        self.assertEqual(len(large), len(small))

    def test_assign_via_post(self):
        bewerber = self._create_bewerber('p', 'G', 1.0)
        response = self.client.post(reverse('assign'), {'fw': bewerber.id, 'land': self.stelle_a.id})
        self.assertRedirects(response, reverse('assign_scroll', args=[self.stelle_a.id]), fetch_redirect_response=False)
        bewerber.refresh_from_db()
        self.assertEqual(bewerber.zuteilung, self.stelle_a)

        response = self.client.post(reverse('assign'), {'fw': bewerber.id, 'land': 'None'})
        self.assertRedirects(response, reverse('assign'), fetch_redirect_response=False)
        bewerber.refresh_from_db()
        self.assertIsNone(bewerber.zuteilung)

    def test_assign_via_get_changes_nothing(self):
        bewerber = self._create_bewerber('g', 'G', 1.0)
        response = self.client.get(reverse('assign') + f'?fw={bewerber.id}&land={self.stelle_a.id}')
        self.assertEqual(response.status_code, 200)
        bewerber.refresh_from_db()
        self.assertIsNone(bewerber.zuteilung)

    def test_assign_invalid_values(self):
        bewerber = self._create_bewerber('i', 'G', 1.0)
        response = self.client.post(reverse('assign'), {'fw': bewerber.id, 'land': 'abc'})
        self.assertRedirects(response, reverse('assign'), fetch_redirect_response=False)
        bewerber.refresh_from_db()
        self.assertIsNone(bewerber.zuteilung)

    def test_auto_assign_and_clear_require_post(self):
        bewerber = self._create_bewerber('a', 'G', 1.0, wish=self.stelle_a)

        self.assertEqual(self.client.get(reverse('auto_assign')).status_code, 405)
        self.assertEqual(self.client.get(reverse('clear_assignments')).status_code, 405)
        bewerber.refresh_from_db()
        self.assertIsNone(bewerber.zuteilung)

        self.client.post(reverse('auto_assign'))
        bewerber.refresh_from_db()
        self.assertEqual(bewerber.zuteilung, self.stelle_a)

        self.client.post(reverse('clear_assignments'))
        bewerber.refresh_from_db()
        self.assertIsNone(bewerber.zuteilung)
