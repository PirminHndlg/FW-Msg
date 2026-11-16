from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from Global.models import CustomUser, PersonCluster
from ORG.models import Organisation

from .models import ApplicationAnswer, ApplicationQuestion, ApplicationText


def make_org(name='Test Org'):
    return Organisation.objects.create(name=name, email=f'{name}@test.de')


def make_bewerber_user(org, username='bewerber1', password='pass1234'):
    user = User.objects.create_user(username=username, password=password)
    cluster = PersonCluster.objects.create(name='Bewerber', org=org, view='B')
    CustomUser.objects.create(user=user, org=org, person_cluster=cluster)
    return user


class ApplicationAnswerDoneTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._register_email_patcher = patch('ORG.tasks.send_register_email_task.s')
        cls._mock_register_email = cls._register_email_patcher.start()
        cls._mock_register_email.return_value.apply_async = MagicMock()

    @classmethod
    def tearDownClass(cls):
        cls._register_email_patcher.stop()
        super().tearDownClass()

    def setUp(self):
        self.org = make_org()
        self.user = make_bewerber_user(self.org)
        self.question = ApplicationQuestion.objects.create(
            org=self.org,
            question='Warum möchtest du mitmachen?',
            order=1,
            max_length=1000,
        )
        ApplicationText.objects.create(
            org=self.org,
            welcome='Willkommen',
            footer='Footer',
            deadline=(timezone.now() + timedelta(days=30)).date(),
        )
        self.client = Client()
        self.client.login(username='bewerber1', password='pass1234')
        self.url = reverse('bw_application_answer', args=[self.question.id])

    def test_mark_done_without_answer_keeps_row(self):
        response = self.client.post(self.url, {'answer': '', 'is_done': 'on'}, follow=True)
        self.assertEqual(response.status_code, 200)

        answer = ApplicationAnswer.objects.get(user=self.user, question=self.question)
        self.assertTrue(answer.is_done)
        self.assertEqual(answer.answer, '')

    def test_empty_answer_without_done_deletes_row(self):
        ApplicationAnswer.objects.create(
            user=self.user,
            org=self.org,
            question=self.question,
            answer='Temporär',
            is_done=False,
        )

        response = self.client.post(self.url, {'answer': ''}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            ApplicationAnswer.objects.filter(user=self.user, question=self.question).exists()
        )

    def test_done_question_appears_in_sidebar_context(self):
        ApplicationAnswer.objects.create(
            user=self.user,
            org=self.org,
            question=self.question,
            answer='Meine Antwort',
            is_done=True,
        )

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertIn(self.question.id, response.context['done_questions_ids'])


class BewerberMailNotificationActionTests(TestCase):
    """Checkbox actions in the Bewerber table that switch mail notifications."""

    def setUp(self):
        # No Celery broker and no real mails during the test
        self.addCleanup(patch.stopall)
        patch('celery.app.task.Task.apply_async').start()
        self.smtp = patch('Global.send_email.send_mail', return_value=1).start()

        from .models import Bewerber

        self.org = make_org('Mail Action Org')
        self.org_user = User.objects.get(customuser__org=self.org)
        self.client.force_login(self.org_user)

        self.bewerber = []
        for i in range(3):
            user = make_bewerber_user(self.org, username=f'bw{i}')
            bewerber, _ = Bewerber.objects.get_or_create(user=user, defaults={'org': self.org})
            self.bewerber.append(bewerber)

    def run_action(self, action, bewerber):
        return self.client.get(
            reverse('list_object_checkbox', args=['bewerber']),
            {'checkbox': [b.id for b in bewerber], 'checkbox_submit_value': action},
        )

    def mail_flags(self):
        return [CustomUser.objects.get(user=b.user).mail_notifications for b in self.bewerber]

    def test_actions_are_offered(self):
        from .models import Bewerber
        keys = [choice[0] for choice in Bewerber.CHECKBOX_ACTION_CHOICES]
        self.assertIn('enable_mail_notifications', keys)
        self.assertIn('disable_mail_notifications', keys)

    def test_disable_only_selected(self):
        response = self.run_action('disable_mail_notifications', self.bewerber[:2])
        self.assertRedirects(response, reverse('list_object', args=['bewerber']), fetch_redirect_response=False)
        self.assertEqual(self.mail_flags(), [False, False, True])

    def test_enable_selected(self):
        CustomUser.objects.filter(user__in=[b.user for b in self.bewerber]).update(mail_notifications=False)
        self.run_action('enable_mail_notifications', self.bewerber[1:])
        self.assertEqual(self.mail_flags(), [False, True, True])

    def test_enable_keeps_per_type_preferences(self):
        from Global.notifications import EMAIL, NotificationType, get_channel_setting, set_preference
        user = self.bewerber[0].user
        set_preference(user, NotificationType.POST, EMAIL, False)
        self.run_action('disable_mail_notifications', [self.bewerber[0]])
        self.run_action('enable_mail_notifications', [self.bewerber[0]])
        user = User.objects.get(pk=user.pk)
        self.assertTrue(user.customuser.mail_notifications)
        self.assertFalse(get_channel_setting(user, NotificationType.POST, EMAIL))

    def test_actions_send_no_mail(self):
        self.run_action('disable_mail_notifications', self.bewerber)
        self.run_action('enable_mail_notifications', self.bewerber)
        self.smtp.assert_not_called()

    def test_other_org_cannot_change_flags(self):
        other_org = make_org('Other Mail Org')
        self.client.force_login(User.objects.get(customuser__org=other_org))
        self.run_action('disable_mail_notifications', self.bewerber)
        self.assertEqual(self.mail_flags(), [True, True, True])

    def test_requires_org_role(self):
        self.client.force_login(self.bewerber[0].user)
        self.run_action('disable_mail_notifications', self.bewerber)
        self.assertEqual(self.mail_flags(), [True, True, True])
