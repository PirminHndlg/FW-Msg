from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from PIL import Image
from io import BytesIO
from django.core.files.uploadedfile import SimpleUploadedFile

from BW.models import Bewerber
from FW.models import Freiwilliger
from Global.models import CustomUser, Einsatzland2, PersonCluster
from Home.forms import OwnSigninForm
from Home.models import OwnSigninUser
from Home.own_signin_service import (
    OwnSigninApprovalError,
    approve_own_signin_user,
    deny_own_signin_user,
)
from ORG.models import Organisation

User = get_user_model()


class OwnSigninTestCase(TestCase):
    def setUp(self):
        image = Image.new('RGB', (1, 1), color='red')
        image_io = BytesIO()
        image.save(image_io, format='JPEG')
        image_io.seek(0)
        logo_img = SimpleUploadedFile(
            name='test_logo.png',
            content=image_io.read(),
            content_type='image/png',
        )

        self.org = Organisation.objects.create(
            name='Test Org',
            email='org@test.com',
            logo=logo_img,
        )
        self.land = Einsatzland2.objects.create(org=self.org, name='Testland', code='TL')
        self.person_cluster = PersonCluster.objects.create(
            org=self.org,
            name='Freiwillige 2026',
            view='F',
            own_signin_token='test-token-123',
        )
        self.org_cluster = PersonCluster.objects.create(
            org=self.org,
            name='Organisation',
            view='O',
        )
        self.org_user = User.objects.create_user(
            username='orgadmin',
            email='admin@test.com',
            password='testpass123',
            first_name='Org',
            last_name='Admin',
        )
        CustomUser.objects.create(
            user=self.org_user,
            org=self.org,
            person_cluster=self.org_cluster,
        )
        self.client = Client()

    def _create_pending_signup(self, email='newuser@test.com'):
        return OwnSigninUser.objects.create(
            org=self.org,
            first_name='New',
            last_name='User',
            email=email,
            person_cluster=self.person_cluster,
            land=self.land,
        )

    def test_form_save_creates_own_signin_user_not_user(self):
        form = OwnSigninForm(
            org=self.org,
            person_cluster=self.person_cluster,
            data={
                'first_name': 'New',
                'last_name': 'User',
                'email': 'signup@test.com',
                'land': self.land.id,
            },
        )
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.assertEqual(OwnSigninUser.objects.count(), 1)
        self.assertEqual(User.objects.filter(email='signup@test.com').count(), 0)

    def test_form_rejects_duplicate_email_as_user(self):
        User.objects.create_user(
            username='existing',
            email='existing@test.com',
            password='testpass123',
        )
        form = OwnSigninForm(
            org=self.org,
            person_cluster=self.person_cluster,
            data={
                'first_name': 'New',
                'last_name': 'User',
                'email': 'existing@test.com',
                'land': self.land.id,
            },
        )
        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)

    def test_form_rejects_duplicate_pending_email(self):
        self._create_pending_signup('pending@test.com')
        form = OwnSigninForm(
            org=self.org,
            person_cluster=self.person_cluster,
            data={
                'first_name': 'Other',
                'last_name': 'User',
                'email': 'pending@test.com',
                'land': self.land.id,
            },
        )
        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)

    @patch('Home.tasks.send_own_signin_accepted_email_task.delay')
    def test_approve_creates_user_role_and_deletes_pending(self, mock_accepted_email):
        pending = self._create_pending_signup()
        user = approve_own_signin_user(pending)
        self.assertEqual(user.email, 'newuser@test.com')
        self.assertTrue(CustomUser.objects.filter(user=user, org=self.org).exists())
        self.assertTrue(Freiwilliger.objects.filter(user=user, org=self.org).exists())
        freiwilliger = Freiwilliger.objects.get(user=user)
        self.assertEqual(freiwilliger.einsatzland2, self.land)
        self.assertEqual(OwnSigninUser.objects.count(), 0)
        mock_accepted_email.assert_called_once()

    def test_approve_raises_if_user_already_exists(self):
        User.objects.create_user(
            username='existing',
            email='newuser@test.com',
            password='testpass123',
        )
        pending = self._create_pending_signup()
        with self.assertRaises(OwnSigninApprovalError):
            approve_own_signin_user(pending)
        self.assertEqual(OwnSigninUser.objects.count(), 1)

    @patch('Home.tasks.send_own_signin_denied_email_task.delay')
    def test_deny_deletes_pending(self, mock_denied_email):
        pending = self._create_pending_signup()
        deny_own_signin_user(pending)
        self.assertEqual(OwnSigninUser.objects.count(), 0)
        mock_denied_email.assert_called_once()

    @patch('Home.tasks.send_own_signin_org_notification_task.delay')
    def test_own_signin_view_saves_and_queues_notification(self, mock_notify):
        response = self.client.post(
            reverse('own_signin', kwargs={'token': 'test-token-123'}),
            data={
                'first_name': 'Web',
                'last_name': 'User',
                'email': 'web@test.com',
                'land': self.land.id,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(OwnSigninUser.objects.count(), 1)
        mock_notify.assert_called_once()

    @patch('Home.tasks.send_own_signin_accepted_email_task.delay')
    def test_org_approve_view(self, mock_accepted_email):
        pending = self._create_pending_signup()
        self.client.login(username='orgadmin', password='testpass123')
        response = self.client.post(
            reverse('approve_own_signin_user', kwargs={'pk': pending.pk}),
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(OwnSigninUser.objects.count(), 0)
        self.assertTrue(User.objects.filter(email='newuser@test.com').exists())

    @patch('Home.tasks.send_own_signin_denied_email_task.delay')
    def test_org_deny_view(self, mock_denied_email):
        pending = self._create_pending_signup()
        self.client.login(username='orgadmin', password='testpass123')
        response = self.client.post(
            reverse('deny_own_signin_user', kwargs={'pk': pending.pk}),
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(OwnSigninUser.objects.count(), 0)

    def test_org_cannot_approve_other_org_request(self):
        other_org = Organisation.objects.create(name='Other Org', email='other@test.com')
        other_cluster = PersonCluster.objects.create(org=other_org, name='FW', view='F')
        pending = OwnSigninUser.objects.create(
            org=other_org,
            first_name='Other',
            last_name='User',
            email='otheruser@test.com',
            person_cluster=other_cluster,
        )
        self.client.login(username='orgadmin', password='testpass123')
        response = self.client.post(
            reverse('approve_own_signin_user', kwargs={'pk': pending.pk}),
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(OwnSigninUser.objects.count(), 1)
