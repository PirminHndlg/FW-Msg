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
