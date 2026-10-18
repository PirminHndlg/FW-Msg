from datetime import timedelta

from django.contrib.auth.models import User
from django.test import Client, SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from ORG.models import Organisation

from .deeptalk import (
    MAX_INPUT_CHARS, MAX_QUESTION_LENGTH, MAX_QUESTIONS_PER_IMPORT,
    get_question_for_date, normalize_for_compare, parse_questions,
)
from .models import CustomUser, DeepTalkFrage, DeepTalkTag, PersonCluster


class ParseQuestionsTests(SimpleTestCase):

    def test_one_question_per_line(self):
        result = parse_questions('Was macht dich glücklich?\nWovor hast du Angst?')
        self.assertEqual(result.questions, ['Was macht dich glücklich?', 'Wovor hast du Angst?'])

    def test_blank_lines_between_questions(self):
        result = parse_questions('Erste Frage hier?\n\n\nZweite Frage hier?\n   \nDritte Frage hier?')
        self.assertEqual(len(result.questions), 3)

    def test_windows_and_unicode_line_breaks(self):
        result = parse_questions('Frage eins hier?\r\nFrage zwei hier?\rFrage drei hier? Frage vier hier?')
        self.assertEqual(len(result.questions), 4)

    def test_bullets_and_numbering_are_removed(self):
        text = '- Erste Frage?\n• Zweite Frage?\n1. Dritte Frage?\n2) Vierte Frage?\n(3) Fünfte Frage?\nFrage 6: Sechste Frage?\na) Siebte Frage?'
        result = parse_questions(text)
        self.assertEqual(result.questions, [
            'Erste Frage?', 'Zweite Frage?', 'Dritte Frage?', 'Vierte Frage?',
            'Fünfte Frage?', 'Sechste Frage?', 'Siebte Frage?',
        ])

    def test_abbreviation_at_start_is_kept(self):
        result = parse_questions('z.B. was würdest du tun?')
        self.assertEqual(result.questions, ['z.B. was würdest du tun?'])

    def test_table_number_column_is_removed(self):
        result = parse_questions('1\tWas ist dir wichtig?\n2\tWas tut dir gut?')
        self.assertEqual(result.questions, ['Was ist dir wichtig?', 'Was tut dir gut?'])

    def test_wrapped_question_is_joined(self):
        result = parse_questions('Wenn du einen Tag lang\nunsichtbar wärst, was würdest du tun?\nNächste Frage hier?')
        self.assertEqual(result.questions, [
            'Wenn du einen Tag lang unsichtbar wärst, was würdest du tun?',
            'Nächste Frage hier?',
        ])

    def test_lines_starting_uppercase_are_not_joined(self):
        result = parse_questions('Erzähl von deinem Tag\nWas war schön')
        self.assertEqual(len(result.questions), 2)

    def test_multiple_questions_in_one_line(self):
        result = parse_questions('Was macht dich stark? Wann fühlst du dich frei? Wen vermisst du?')
        self.assertEqual(len(result.questions), 3)

    def test_sentence_with_question_is_not_split(self):
        result = parse_questions('Warum? Erzähl mehr darüber.')
        self.assertEqual(result.questions, ['Warum? Erzähl mehr darüber.'])

    def test_quotes_and_whitespace_are_cleaned(self):
        result = parse_questions('  „Was  bedeutet  Heimat für dich?“  \n"Was ist Glück?"')
        self.assertEqual(result.questions, ['Was bedeutet Heimat für dich?', 'Was ist Glück?'])

    def test_invisible_and_control_characters_are_removed(self):
        result = parse_questions('Was​ ist\u0007 dir﻿ wichtig?‮')
        self.assertEqual(result.questions, ['Was ist dir wichtig?'])

    def test_duplicates_in_input_and_existing(self):
        existing = {normalize_for_compare('Was ist dir wichtig?')}
        result = parse_questions('was ist dir WICHTIG\nNeue Frage hier?\nneue frage hier?', existing_normalized=existing)
        self.assertEqual(result.questions, ['Neue Frage hier?'])
        self.assertEqual(len(result.duplicates), 2)

    def test_too_short_and_too_long(self):
        result = parse_questions('Ja?\n' + 'x' * (MAX_QUESTION_LENGTH + 1) + '\nGültige Frage?')
        self.assertEqual(result.questions, ['Gültige Frage?'])
        self.assertEqual(len(result.too_short), 1)
        self.assertEqual(len(result.too_long), 1)

    def test_input_and_count_limits(self):
        many = '\n'.join(f'Frage Nummer {i}?' for i in range(MAX_QUESTIONS_PER_IMPORT + 50))
        result = parse_questions(many)
        self.assertEqual(len(result.questions), MAX_QUESTIONS_PER_IMPORT)
        self.assertTrue(result.limit_reached)
        self.assertTrue(parse_questions('a' * (MAX_INPUT_CHARS + 10)).truncated_input)

    def test_html_is_kept_as_plain_text(self):
        result = parse_questions('<script>alert(1)</script> Was nun?')
        self.assertEqual(result.questions, ['<script>alert(1)</script> Was nun?'])

    def test_pathological_input_is_fast(self):
        # Viele Präfix- und Satzzeichen: darf nicht in exponentielles Backtracking laufen
        result = parse_questions(('-' * 5000 + ' ' + '?' * 5000 + '\n') * 5)
        self.assertIsNotNone(result)


class QuestionOfTheDayTests(TestCase):

    def setUp(self):
        self.org = Organisation.objects.create(name='Org A')
        self.other_org = Organisation.objects.create(name='Org B')
        self.today = timezone.localdate()

    def _fragen(self, count, org=None):
        start = DeepTalkFrage.objects.count()
        return [DeepTalkFrage.objects.create(org=org or self.org, text=f'Frage Nummer {start + i}?') for i in range(count)]

    def test_no_questions(self):
        self.assertIsNone(get_question_for_date(self.org))

    def test_same_question_all_day(self):
        self._fragen(5)
        first = get_question_for_date(self.org)
        self.assertEqual(get_question_for_date(self.org), first)
        self.assertEqual(DeepTalkTag.objects.filter(org=self.org, datum=self.today).count(), 1)

    def test_new_questions_do_not_change_todays_question(self):
        self._fragen(2)
        first = get_question_for_date(self.org)
        self._fragen(10)
        self.assertEqual(get_question_for_date(self.org), first)

    def test_all_questions_before_repeat(self):
        fragen = self._fragen(5)
        shown = [get_question_for_date(self.org, self.today - timedelta(days=offset)).id for offset in range(4, -1, -1)]
        self.assertEqual(sorted(shown), sorted(frage.id for frage in fragen))

    def test_repeats_after_cycle_but_not_twice_in_a_row(self):
        self._fragen(3)
        shown = [get_question_for_date(self.org, self.today - timedelta(days=offset)).id for offset in range(29, -1, -1)]
        self.assertTrue(all(a != b for a, b in zip(shown, shown[1:])))
        self.assertEqual(len(set(shown)), 3)

    def test_inactive_questions_are_not_chosen(self):
        active, inactive = self._fragen(2)
        inactive.active = False
        inactive.save()
        self.assertEqual(get_question_for_date(self.org), active)

    def test_deactivating_todays_question_picks_another(self):
        self._fragen(2)
        first = get_question_for_date(self.org)
        first.active = False
        first.save()
        self.assertNotEqual(get_question_for_date(self.org), first)

    def test_organisations_are_separate(self):
        own = self._fragen(1)[0]
        self._fragen(1, org=self.other_org)
        self.assertEqual(get_question_for_date(self.org), own)

    def test_future_dates_are_not_assigned(self):
        self._fragen(2)
        self.assertIsNone(get_question_for_date(self.org, self.today + timedelta(days=1)))
        self.assertFalse(DeepTalkTag.objects.exists())

    def test_duplicate_text_per_org_is_rejected(self):
        from django.db import IntegrityError
        DeepTalkFrage.objects.create(org=self.org, text='Was ist dir wichtig?')
        DeepTalkFrage.objects.create(org=self.other_org, text='Was ist dir wichtig?')
        with self.assertRaises(IntegrityError):
            DeepTalkFrage.objects.create(org=self.org, text='was ist dir wichtig')


class DeepTalkViewTests(TestCase):

    def setUp(self):
        self.org = Organisation.objects.create(name='Org A')
        self.other_org = Organisation.objects.create(name='Org B')
        org_cluster = PersonCluster.objects.create(org=self.org, name='Org', view='O')
        fw_cluster = PersonCluster.objects.create(org=self.org, name='FW', view='F')
        self.org_user = self._user('deeptalk_org', self.org, org_cluster)
        self.fw_user = self._user('deeptalk_fw', self.org, fw_cluster)
        self.client = Client()

    def _user(self, username, org, cluster):
        user = User.objects.create_user(username=username, password='testpass123')
        CustomUser.objects.create(user=user, org=org, person_cluster=cluster)
        return user

    def _post(self, data):
        return self.client.post(reverse('deeptalk_fragen'), data)

    def test_volunteer_sees_question_on_hub_and_page(self):
        DeepTalkFrage.objects.create(org=self.org, text='Was gibt dir Kraft?')
        DeepTalkFrage.objects.create(org=self.other_org, text='Fremde Frage der anderen Org?')
        self.client.force_login(self.fw_user)
        for url in (reverse('impulse'), reverse('deeptalk')):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, 'Was gibt dir Kraft?')
            self.assertNotContains(response, 'Fremde Frage')

    def test_question_text_is_escaped(self):
        DeepTalkFrage.objects.create(org=self.org, text='<script>alert("x")</script> Was nun?')
        self.client.force_login(self.fw_user)
        response = self.client.get(reverse('impulse'))
        self.assertNotContains(response, '<script>alert("x")</script>')
        self.assertContains(response, '&lt;script&gt;')

    def test_hub_requires_login(self):
        self.assertEqual(self.client.get(reverse('impulse')).status_code, 302)

    def test_volunteer_cannot_manage_questions(self):
        self.client.force_login(self.fw_user)
        self._post({'action': 'save', 'fragen': 'Neue Frage hier?'})
        self.assertFalse(DeepTalkFrage.objects.exists())

    def test_preview_does_not_save(self):
        self.client.force_login(self.org_user)
        response = self._post({'action': 'preview', 'fragen': '1. Erste Frage?\n\n2. Zweite Frage?'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['preview'].questions, ['Erste Frage?', 'Zweite Frage?'])
        self.assertFalse(DeepTalkFrage.objects.exists())

    def test_save_bulk_and_skip_existing(self):
        DeepTalkFrage.objects.create(org=self.org, text='Erste Frage?')
        self.client.force_login(self.org_user)
        response = self._post({'action': 'save', 'fragen': 'Erste Frage?\nZweite Frage?\nDritte Frage?'})
        self.assertRedirects(response, reverse('deeptalk_fragen'))
        self.assertEqual(DeepTalkFrage.objects.filter(org=self.org).count(), 3)
        self.assertTrue(all(f.text_normalized for f in DeepTalkFrage.objects.all()))

    def test_toggle_and_delete_only_own_org(self):
        own = DeepTalkFrage.objects.create(org=self.org, text='Eigene Frage?')
        foreign = DeepTalkFrage.objects.create(org=self.other_org, text='Fremde Frage?')
        self.client.force_login(self.org_user)

        self._post({'action': 'toggle', 'frage_id': own.id})
        own.refresh_from_db()
        self.assertFalse(own.active)

        self._post({'action': 'delete', 'frage_id': foreign.id})
        self._post({'action': 'toggle', 'frage_id': foreign.id})
        foreign.refresh_from_db()
        self.assertTrue(foreign.active)

        self._post({'action': 'delete', 'frage_id': own.id})
        self.assertFalse(DeepTalkFrage.objects.filter(id=own.id).exists())

    def test_invalid_ids_are_handled(self):
        self.client.force_login(self.org_user)
        response = self._post({'action': 'delete', 'frage_id': '1 OR 1=1'})
        self.assertRedirects(response, reverse('deeptalk_fragen'))

    def test_management_page_renders(self):
        DeepTalkFrage.objects.create(org=self.org, text='Eine Frage?')
        self.client.force_login(self.org_user)
        response = self.client.get(reverse('deeptalk_fragen'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Eine Frage?')
