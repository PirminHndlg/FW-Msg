import json
from unittest.mock import patch

import requests
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from pywebpush import WebPushException

from ORG.models import Organisation

from .models import PushSubscription
from .push_notification import (
    PUSH_BODY_MAX_CHARS,
    PUSH_REQUEST_TIMEOUT_SECONDS,
    PUSH_TTL_SECONDS,
    send_push_notification,
)


def _error_response(status_code):
    response = requests.Response()
    response.status_code = status_code
    return response


@override_settings(VAPID_PRIVATE_KEY='test-private-key', SERVER_EMAIL='server@example.com')
class SendPushNotificationTests(TestCase):
    def setUp(self):
        with patch('ORG.tasks.send_register_email_task'):
            self.org = Organisation.objects.create(
                name='Push test org',
                email='org@example.com',
            )
        self.user = User.objects.get(customuser__org=self.org)
        self.subscription = PushSubscription.objects.create(
            user=self.user,
            org=self.org,
            endpoint='https://push.example.com/abc',
            p256dh='p256dh-key',
            auth='auth-secret',
        )

    @patch('Global.push_notification.webpush')
    def test_sends_with_ttl_urgency_and_timeout(self, mock_webpush):
        self.assertTrue(send_push_notification(self.subscription, 'Titel', 'Grüße'))

        kwargs = mock_webpush.call_args.kwargs
        self.assertEqual(kwargs['ttl'], PUSH_TTL_SECONDS)
        self.assertGreater(kwargs['ttl'], 0)
        self.assertEqual(kwargs['headers'], {'Urgency': 'high'})
        self.assertEqual(kwargs['timeout'], PUSH_REQUEST_TIMEOUT_SECONDS)
        # Umlauts are sent as UTF-8, not as \u escapes.
        self.assertIn('Grüße', kwargs['data'])

        self.subscription.refresh_from_db()
        self.assertIsNotNone(self.subscription.last_used)

    @patch('Global.push_notification.webpush')
    def test_long_body_is_truncated(self, mock_webpush):
        send_push_notification(self.subscription, 'Titel', 'x' * 5000)

        data = json.loads(mock_webpush.call_args.kwargs['data'])
        self.assertEqual(len(data['body']), PUSH_BODY_MAX_CHARS)
        self.assertTrue(data['body'].endswith('…'))

    @patch('Global.push_notification.webpush')
    def test_short_body_is_unchanged(self, mock_webpush):
        send_push_notification(self.subscription, 'Titel', 'Hallo')

        data = json.loads(mock_webpush.call_args.kwargs['data'])
        self.assertEqual(data['body'], 'Hallo')

    def _assert_subscription_deleted_on(self, status_code):
        with patch('Global.push_notification.webpush') as mock_webpush:
            mock_webpush.side_effect = WebPushException('gone', response=_error_response(status_code))
            self.assertFalse(send_push_notification(self.subscription, 'Titel', 'Text'))
        self.assertFalse(PushSubscription.objects.filter(pk=self.subscription.pk).exists())

    def test_404_deletes_subscription(self):
        self._assert_subscription_deleted_on(404)

    def test_410_deletes_subscription(self):
        self._assert_subscription_deleted_on(410)

    @patch('Global.push_notification.webpush')
    def test_other_errors_keep_subscription(self, mock_webpush):
        mock_webpush.side_effect = WebPushException('too many', response=_error_response(429))

        self.assertFalse(send_push_notification(self.subscription, 'Titel', 'Text'))
        self.assertTrue(PushSubscription.objects.filter(pk=self.subscription.pk).exists())

    @patch('Global.push_notification.webpush')
    def test_error_without_response_keeps_subscription(self, mock_webpush):
        mock_webpush.side_effect = WebPushException('network', response=None)

        self.assertFalse(send_push_notification(self.subscription, 'Titel', 'Text'))
        self.assertTrue(PushSubscription.objects.filter(pk=self.subscription.pk).exists())
