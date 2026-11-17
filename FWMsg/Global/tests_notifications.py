"""
Tests for per-user notification preferences (Global.notifications).

No email ever leaves the test and no Celery broker is needed:

* ``Global.send_email.send_mail`` (the low-level SMTP call every
  ``send_email_with_archive`` goes through) and the IMAP archive are patched.
* ``Global.push_notification.webpush`` is patched; push still runs through the
  real ``send_push_notification_to_user`` with real ``PushSubscription`` rows,
  so the tests see which device would have been notified.
* ``celery.app.task.Task.apply_async`` is patched globally, so ``.delay()``,
  ``.s().apply_async()`` etc. only record the call. Task bodies are called
  directly as plain functions.
"""
import json
import re
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from chat.models import ChatDirect, ChatGroup, ChatMessageDirect, ChatMessageGroup
from FW.models import Freiwilliger
from ORG.models import Organisation
from TEAM.models import Team

from .models import (
    Ampel2,
    AmpelConfiguration,
    Aufgabe2,
    ChangeRequest,
    CustomUser,
    Einsatzland2,
    KalenderEvent,
    NotificationPreference,
    PersonCluster,
    Post2,
    PostResponse,
    PushSubscription,
    UserAufgaben,
)
from .notifications import (
    EMAIL,
    NOTIFICATION_SPECS,
    PUSH,
    NotificationType,
    filter_users_wanting,
    get_channel_setting,
    get_type_unsubscribe_url,
    notify_user,
    set_preference,
    visible_specs_for,
    wants_notification,
)

PUSH_ENDPOINT = 'https://push.invalid/'


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    VAPID_PRIVATE_KEY='test-vapid-key',
    CELERY_TASK_ALWAYS_EAGER=False,
)
class NotificationTestBase(TestCase):
    """Isolates every outgoing channel and provides users with push devices."""

    def setUp(self):
        self.celery = patch('celery.app.task.Task.apply_async').start()
        self.smtp = patch('Global.send_email.send_mail', return_value=1).start()
        self.imap = patch('Global.send_email.save_email_to_sent_folder').start()
        self.webpush = patch('Global.push_notification.webpush').start()
        self.addCleanup(patch.stopall)

        self.org = Organisation.objects.create(name='Notification org', email='org@example.com')
        self.org_user = User.objects.get(customuser__org=self.org)

        self.fw_cluster = PersonCluster.objects.create(
            org=self.org, name='FW', view='F', aufgaben=True, calendar=True, ampel=True,
        )
        self.team_cluster = PersonCluster.objects.create(org=self.org, name='Team', view='T')
        self.orga_cluster = PersonCluster.objects.create(org=self.org, name='Orga', view='O')

        self.fw_user = self.make_user('fw', self.fw_cluster)
        self.team_user = self.make_user('team', self.team_cluster)
        self.reset_outgoing()

    def tearDown(self):
        # Safety net: nothing may have reached Django's mail backend.
        self.assertEqual(mail.outbox, [])

    # -- helpers ---------------------------------------------------------
    def make_user(self, name, cluster, push=True):
        user = User.objects.create_user(
            username=name, email=f'{name}@example.com', first_name=name.title(), last_name='Test',
        )
        CustomUser.objects.create(user=user, org=self.org, person_cluster=cluster)
        if push:
            PushSubscription.objects.create(
                user=user, org=self.org, endpoint=f'{PUSH_ENDPOINT}{name}', p256dh='p', auth='a',
            )
        return User.objects.get(pk=user.pk)

    def fresh(self, user):
        """Reload a user so the per-instance preference cache is empty."""
        return User.objects.get(pk=user.pk)

    def reset_outgoing(self):
        self.smtp.reset_mock()
        self.webpush.reset_mock()
        self.celery.reset_mock()

    def mail_recipients(self):
        recipients = set()
        for call in self.smtp.call_args_list:
            recipients.update(call.kwargs['recipient_list'])
        return recipients

    def push_usernames(self):
        return {
            call.kwargs['subscription_info']['endpoint'].removeprefix(PUSH_ENDPOINT)
            for call in self.webpush.call_args_list
        }

    def push_payloads(self):
        return [json.loads(call.kwargs['data']) for call in self.webpush.call_args_list]

    def disable(self, user, notification_type, *channels):
        for channel in channels:
            set_preference(user, notification_type, channel, False)

    def mail_master_off(self, user):
        user.customuser.mail_notifications = False
        user.customuser.save()


class IsolationTests(NotificationTestBase):
    """Guards for the test setup itself."""

    def test_celery_dispatch_is_only_recorded(self):
        Post2.objects.create(org=self.org, user=self.org_user, title='T', text='x')
        self.assertTrue(self.celery.called)
        self.smtp.assert_not_called()
        self.webpush.assert_not_called()

    def test_send_email_with_archive_never_reaches_backend(self):
        from .send_email import send_email_with_archive
        send_email_with_archive('S', 'body', 'from@example.com', ['to@example.com'])
        self.smtp.assert_called_once()
        self.imap.assert_called_once()


class RegistryTests(NotificationTestBase):
    def test_every_type_has_a_spec(self):
        self.assertEqual(set(NOTIFICATION_SPECS), set(NotificationType.values))

    def test_every_spec_has_valid_channels_and_defaults(self):
        for spec in NOTIFICATION_SPECS.values():
            self.assertTrue(spec.channels, spec.type)
            self.assertTrue(set(spec.channels) <= {EMAIL, PUSH}, spec.type)
            for channel in spec.channels:
                self.assertIn(channel, spec.defaults, spec.type)

    def test_type_unsubscribe_url_contains_type(self):
        url = get_type_unsubscribe_url(self.fw_user, NotificationType.POST)
        self.assertTrue(url.endswith('?type=post'))
        self.assertIn(str(self.fw_user.id), url)


class PreferenceLogicTests(NotificationTestBase):
    def test_defaults_without_row(self):
        for notification_type in NotificationType.values:
            self.assertTrue(wants_notification(self.fw_user, notification_type, EMAIL))
            self.assertTrue(wants_notification(self.fw_user, notification_type, PUSH))
        self.assertFalse(NotificationPreference.objects.exists())

    def test_set_preference_creates_single_row_and_keeps_other_channel(self):
        set_preference(self.fw_user, NotificationType.POST, EMAIL, False)
        set_preference(self.fw_user, NotificationType.POST, EMAIL, False)
        pref = NotificationPreference.objects.get(user=self.fw_user)
        self.assertFalse(pref.email)
        self.assertTrue(pref.push)
        self.assertEqual(pref.org, self.org)

    def test_set_preference_is_per_type_and_channel(self):
        set_preference(self.fw_user, NotificationType.POST, EMAIL, False)
        user = self.fresh(self.fw_user)
        self.assertFalse(wants_notification(user, NotificationType.POST, EMAIL))
        self.assertTrue(wants_notification(user, NotificationType.POST, PUSH))
        self.assertTrue(wants_notification(user, NotificationType.CHAT_DIRECT, EMAIL))
        self.assertTrue(wants_notification(self.team_user, NotificationType.POST, EMAIL))

    def test_preference_can_be_switched_back_on(self):
        set_preference(self.fw_user, NotificationType.POST, PUSH, False)
        set_preference(self.fw_user, NotificationType.POST, PUSH, True)
        self.assertTrue(wants_notification(self.fresh(self.fw_user), NotificationType.POST, PUSH))

    def test_set_preference_rejects_unknown_type(self):
        with self.assertRaises(KeyError):
            set_preference(self.fw_user, 'does_not_exist', EMAIL, False)

    def test_mail_master_switch_overrides_email_only(self):
        self.mail_master_off(self.fw_user)
        user = self.fresh(self.fw_user)
        self.assertFalse(wants_notification(user, NotificationType.POST, EMAIL))
        self.assertTrue(wants_notification(user, NotificationType.POST, PUSH))
        # The user's own per-type choice stays untouched
        self.assertTrue(get_channel_setting(user, NotificationType.POST, EMAIL))

    def test_no_email_address_means_no_email(self):
        self.fw_user.email = ''
        self.fw_user.save()
        self.assertFalse(wants_notification(self.fresh(self.fw_user), NotificationType.POST, EMAIL))

    def test_none_user(self):
        self.assertFalse(wants_notification(None, NotificationType.POST, PUSH))

    def test_filter_users_wanting(self):
        other = self.make_user('other', self.team_cluster)
        set_preference(other, NotificationType.TEAM_TASK_DONE, PUSH, False)
        users = User.objects.filter(pk__in=[self.team_user.pk, other.pk])

        self.assertEqual(set(filter_users_wanting(users, NotificationType.TEAM_TASK_DONE, PUSH)), {self.team_user})
        self.assertEqual(set(filter_users_wanting(users, NotificationType.TEAM_TASK_DONE, EMAIL)), {self.team_user, other})

        self.mail_master_off(other)
        self.assertEqual(set(filter_users_wanting(users, NotificationType.TEAM_TASK_DONE, EMAIL)), {self.team_user})

    def test_filter_ignores_preferences_of_other_types(self):
        set_preference(self.team_user, NotificationType.POST, EMAIL, False)
        users = User.objects.filter(pk=self.team_user.pk)
        self.assertEqual(list(filter_users_wanting(users, NotificationType.TEAM_TASK_DONE, EMAIL)), [self.team_user])

    def test_visibility_by_role_and_cluster_flag(self):
        fw_types = {s.type for s in visible_specs_for(self.fw_user)}
        team_types = {s.type for s in visible_specs_for(self.team_user)}
        orga_types = {s.type for s in visible_specs_for(self.make_user('orga', self.orga_cluster))}

        self.assertIn(NotificationType.AMPEL_REMINDER, fw_types)
        self.assertIn(NotificationType.TASK_REMINDER, fw_types)
        self.assertNotIn(NotificationType.TEAM_TASK_DONE, fw_types)
        self.assertNotIn(NotificationType.CHANGE_REQUEST_DECISION, fw_types)

        self.assertIn(NotificationType.TEAM_TASK_DONE, team_types)
        self.assertIn(NotificationType.TEAM_AMPEL_NEW, team_types)
        self.assertIn(NotificationType.CHAT_DIRECT, team_types)
        self.assertNotIn(NotificationType.AMPEL_REMINDER, team_types)
        self.assertNotIn(NotificationType.CALENDAR_NEW, team_types)

        self.assertIn(NotificationType.CHANGE_REQUEST_DECISION, orga_types)
        self.assertNotIn(NotificationType.TEAM_TASK_DONE, orga_types)

    def test_customuser_task_reminders_enabled(self):
        self.assertTrue(self.fw_user.customuser.task_reminders_enabled)
        self.disable(self.fw_user, NotificationType.TASK_REMINDER, PUSH)
        self.mail_master_off(self.fw_user)
        self.assertFalse(self.fresh(self.fw_user).customuser.task_reminders_enabled)


class NotifyUserTests(NotificationTestBase):
    def send(self, user, notification_type=NotificationType.POST, **kwargs):
        kwargs.setdefault('email_html', '<p>Hallo <b>Welt</b></p>')
        kwargs.setdefault('push_body', 'Hallo Welt')
        return notify_user(self.fresh(user), notification_type, 'Betreff', url='/x/', **kwargs)

    def test_sends_both_by_default(self):
        result = self.send(self.fw_user)
        self.assertEqual(result, {EMAIL: True, PUSH: 1})
        self.assertEqual(self.mail_recipients(), {'fw@example.com'})
        self.assertEqual(self.push_usernames(), {'fw'})
        self.assertEqual(self.push_payloads()[0]['title'], 'Betreff')
        self.assertEqual(self.push_payloads()[0]['url'], '/x/')

    def test_plain_text_part_has_no_html(self):
        self.send(self.fw_user)
        call = self.smtp.call_args
        self.assertEqual(call.kwargs['message'], 'Hallo Welt')
        self.assertEqual(call.kwargs['html_message'], '<p>Hallo <b>Welt</b></p>')

    def test_push_still_sent_when_mail_master_off(self):
        self.mail_master_off(self.fw_user)
        result = self.send(self.fw_user)
        self.assertEqual(result, {EMAIL: False, PUSH: 1})
        self.smtp.assert_not_called()

    def test_mail_still_sent_when_push_disabled(self):
        self.disable(self.fw_user, NotificationType.POST, PUSH)
        result = self.send(self.fw_user)
        self.assertEqual(result, {EMAIL: True, PUSH: 0})
        self.webpush.assert_not_called()

    def test_nothing_sent_when_both_disabled(self):
        self.disable(self.fw_user, NotificationType.POST, EMAIL, PUSH)
        self.assertEqual(self.send(self.fw_user), {EMAIL: False, PUSH: 0})
        self.smtp.assert_not_called()
        self.webpush.assert_not_called()

    def test_without_push_subscription(self):
        user = self.make_user('nopush', self.fw_cluster, push=False)
        self.assertEqual(self.send(user), {EMAIL: True, PUSH: 0})

    def test_channel_skipped_when_no_content_given(self):
        self.assertEqual(self.send(self.fw_user, email_html=None), {EMAIL: False, PUSH: 1})
        self.smtp.assert_not_called()

    def test_reply_to_is_passed(self):
        self.send(self.fw_user, reply_to=['org@example.com'])
        self.assertEqual(self.smtp.call_args.kwargs['reply_to_list'], ['org@example.com'])

    def test_mail_error_does_not_block_push(self):
        self.smtp.side_effect = RuntimeError('smtp down')
        result = self.send(self.fw_user)
        self.assertEqual(result, {EMAIL: False, PUSH: 1})


class ChatNotificationTests(NotificationTestBase):
    def setUp(self):
        super().setUp()
        self.direct = ChatDirect.objects.create(org=self.org)
        self.direct.users.add(self.fw_user, self.team_user)
        self.group = ChatGroup.objects.create(org=self.org, name='Gruppe', created_by=self.team_user)
        self.other = self.make_user('other', self.fw_cluster)
        self.group.users.add(self.fw_user, self.team_user, self.other)
        self.reset_outgoing()

    def send_direct(self, **kwargs):
        from chat.tasks import notify_users_about_new_direct_chat_message
        msg = ChatMessageDirect.objects.create(org=self.org, chat=self.direct, user=self.team_user, message='Hi', **kwargs)
        self.reset_outgoing()
        notify_users_about_new_direct_chat_message(msg.id, self.team_user.id)

    def send_group(self, read_by=()):
        from chat.tasks import notify_users_about_new_group_chat_message
        msg = ChatMessageGroup.objects.create(org=self.org, chat=self.group, user=self.team_user, message='Hallo')
        msg.read_by.add(*read_by)
        self.reset_outgoing()
        notify_users_about_new_group_chat_message(msg.id, self.team_user.id)

    def test_direct_message_reaches_recipient_not_sender(self):
        self.send_direct()
        self.assertEqual(self.mail_recipients(), {'fw@example.com'})
        self.assertEqual(self.push_usernames(), {'fw'})
        self.assertIn('Hi', self.push_payloads()[0]['body'])

    def test_direct_message_respects_preferences(self):
        self.disable(self.fw_user, NotificationType.CHAT_DIRECT, PUSH)
        self.send_direct()
        self.assertEqual(self.mail_recipients(), {'fw@example.com'})
        self.webpush.assert_not_called()

    def test_direct_unsubscribe_link_is_type_specific(self):
        self.send_direct()
        self.assertIn('?type=chat_direct', self.smtp.call_args.kwargs['html_message'])

    def test_direct_group_preference_does_not_affect_direct(self):
        self.disable(self.fw_user, NotificationType.CHAT_GROUP, EMAIL, PUSH)
        self.send_direct()
        self.assertEqual(self.push_usernames(), {'fw'})

    def test_read_direct_message_sends_nothing(self):
        self.send_direct(read=True)
        self.smtp.assert_not_called()
        self.webpush.assert_not_called()

    def test_group_message_respects_each_recipient(self):
        self.disable(self.other, NotificationType.CHAT_GROUP, EMAIL)
        self.send_group()
        self.assertEqual(self.mail_recipients(), {'fw@example.com'})
        self.assertEqual(self.push_usernames(), {'fw', 'other'})

    def test_group_message_skips_users_who_read_it(self):
        self.send_group(read_by=[self.fw_user])
        self.assertEqual(self.push_usernames(), {'other'})

    def test_creating_group_sends_nothing(self):
        """Being added to a new group must never trigger a notification."""
        self.client.force_login(self.team_user)
        response = self.client.post(
            reverse('create_chat_group'),
            {'name': 'Neue Gruppe', 'description': '', 'users': [self.fw_user.pk, self.other.pk]},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(ChatGroup.objects.filter(name='Neue Gruppe').exists())
        self.celery.assert_not_called()
        self.smtp.assert_not_called()
        self.webpush.assert_not_called()

    def test_adding_member_sends_nothing(self):
        newcomer = self.make_user('newcomer', self.fw_cluster)
        self.client.force_login(self.team_user)
        response = self.client.post(
            reverse('manage_chat_group', args=[self.group.get_identifier()]),
            data=json.dumps({'action': 'add_member', 'user_id': newcomer.pk}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(newcomer, self.group.users.all())
        self.celery.assert_not_called()
        self.smtp.assert_not_called()
        self.webpush.assert_not_called()

    def test_no_group_invite_notification_type(self):
        self.assertNotIn('chat_group_invite', NotificationType.values)


class PostNotificationTests(NotificationTestBase):
    def setUp(self):
        super().setUp()
        self.other = self.make_user('other', self.fw_cluster)
        self.post = Post2.objects.create(org=self.org, user=self.org_user, title='Hallo', text='Welt')
        self.post.person_cluster.add(self.fw_cluster)
        self.reset_outgoing()

    def test_new_post_goes_to_cluster(self):
        from .send_email import send_new_post_email
        self.assertEqual(send_new_post_email(self.post.id), 2)
        self.assertEqual(self.mail_recipients(), {'fw@example.com', 'other@example.com'})
        self.assertEqual(self.push_usernames(), {'fw', 'other'})

    def test_new_post_push_even_if_mail_master_off(self):
        """Regression: previously the whole user was skipped when mail was off."""
        from .send_email import send_new_post_email
        self.mail_master_off(self.fw_user)
        send_new_post_email(self.post.id)
        self.assertEqual(self.mail_recipients(), {'other@example.com'})
        self.assertEqual(self.push_usernames(), {'fw', 'other'})

    def test_new_post_respects_type_preference(self):
        from .send_email import send_new_post_email
        self.disable(self.fw_user, NotificationType.POST, EMAIL)
        self.disable(self.other, NotificationType.POST, PUSH)
        send_new_post_email(self.post.id)
        self.assertEqual(self.mail_recipients(), {'other@example.com'})
        self.assertEqual(self.push_usernames(), {'fw'})
        self.assertIn(self.fw_user, self.post.already_sent_to.all())

    def test_new_post_is_not_sent_twice(self):
        from .send_email import send_new_post_email
        send_new_post_email(self.post.id)
        self.reset_outgoing()
        send_new_post_email(self.post.id)
        self.smtp.assert_not_called()
        self.webpush.assert_not_called()

    def test_post_response_respects_preferences(self):
        from .send_email import send_post_response_email
        response = PostResponse.objects.create(org=self.org, user=self.other, original_post=self.post, text='Antwort')
        self.disable(self.fw_user, NotificationType.POST, EMAIL, PUSH)
        self.reset_outgoing()

        send_post_response_email(response.id)

        self.assertEqual(self.mail_recipients(), {'other@example.com'})
        self.assertEqual(self.push_usernames(), {'other'})

    def test_post_and_response_share_one_setting(self):
        from .send_email import send_new_post_email, send_post_response_email
        response = PostResponse.objects.create(org=self.org, user=self.other, original_post=self.post, text='Antwort')
        self.disable(self.fw_user, NotificationType.POST, PUSH)
        self.reset_outgoing()

        send_new_post_email(self.post.id)
        send_post_response_email(response.id)

        self.assertEqual(self.push_usernames(), {'other'})
        self.assertEqual(self.smtp.call_count, 4)
        for call in self.smtp.call_args_list:
            self.assertIn('?type=post', call.kwargs['html_message'])


class CalendarNotificationTests(NotificationTestBase):
    def setUp(self):
        super().setUp()
        now = timezone.now()
        self.event = KalenderEvent.objects.create(
            org=self.org, title='Seminar', start=now + timedelta(days=3), end=now + timedelta(days=4),
        )
        self.event.user.add(self.fw_user)
        self.reset_outgoing()

    def run_task(self, user=None):
        from ORG.tasks import send_mail_calendar_reminder_task
        return send_mail_calendar_reminder_task(self.event.id, (user or self.fw_user).id)

    def test_sends_mail_and_push_and_marks_user(self):
        self.assertTrue(self.run_task())
        self.assertEqual(self.mail_recipients(), {'fw@example.com'})
        self.assertEqual(self.push_usernames(), {'fw'})
        self.assertIn(self.fw_user, self.event.mail_reminder_sent_to.all())

    def test_push_only_when_mail_master_off(self):
        """Regression: previously the task returned before sending push."""
        self.mail_master_off(self.fw_user)
        self.assertTrue(self.run_task())
        self.smtp.assert_not_called()
        self.assertEqual(self.push_usernames(), {'fw'})
        self.assertIn(self.fw_user, self.event.mail_reminder_sent_to.all())

    def test_fully_opted_out_user_is_marked_but_gets_nothing(self):
        self.disable(self.fw_user, NotificationType.CALENDAR_NEW, EMAIL, PUSH)
        self.assertFalse(self.run_task())
        self.smtp.assert_not_called()
        self.webpush.assert_not_called()
        self.assertIn(self.fw_user, self.event.mail_reminder_sent_to.all())

    def test_non_participant_gets_nothing(self):
        self.run_task(self.team_user)
        self.smtp.assert_not_called()
        self.webpush.assert_not_called()

    def test_already_reminded_user_gets_nothing(self):
        self.event.mail_reminder_sent_to.add(self.fw_user)
        self.run_task()
        self.smtp.assert_not_called()
        self.webpush.assert_not_called()


class TaskNotificationTests(NotificationTestBase):
    def setUp(self):
        super().setUp()
        self.aufgabe = Aufgabe2.objects.create(org=self.org, name='Bericht', beschreibung='Schreiben')
        self.aufgabe.person_cluster.add(self.fw_cluster)
        self.user_aufgabe = UserAufgaben.objects.create(
            org=self.org, user=self.fw_user, aufgabe=self.aufgabe, faellig=timezone.localdate() + timedelta(days=5),
        )
        self.reset_outgoing()

    def new_tasks(self):
        from .send_email import send_new_aufgaben_email
        result = send_new_aufgaben_email(UserAufgaben.objects.filter(pk=self.user_aufgabe.pk), self.org)
        self.user_aufgabe.refresh_from_db()
        return result

    def test_new_tasks_default(self):
        self.assertTrue(self.new_tasks())
        self.assertEqual(self.mail_recipients(), {'fw@example.com'})
        self.assertEqual(self.push_usernames(), {'fw'})
        self.assertIsNotNone(self.user_aufgabe.last_reminder)

    def test_new_tasks_opted_out_of_mail_still_enter_reminder_cycle(self):
        """Regression: previously last_reminder stayed empty and push repeated daily."""
        self.disable(self.fw_user, NotificationType.TASK_NEW, EMAIL)
        self.assertTrue(self.new_tasks())
        self.smtp.assert_not_called()
        self.assertEqual(self.push_usernames(), {'fw'})
        self.assertIsNotNone(self.user_aufgabe.last_reminder)

    def test_new_tasks_failed_mail_is_retried(self):
        self.smtp.return_value = 0
        self.assertFalse(self.new_tasks())
        self.assertIsNone(self.user_aufgabe.last_reminder)

    def test_task_reminder_respects_preferences(self):
        from .send_email import send_aufgaben_email
        self.disable(self.fw_user, NotificationType.TASK_REMINDER, EMAIL)
        self.assertTrue(send_aufgaben_email(self.user_aufgabe, self.org))
        self.smtp.assert_not_called()
        self.assertEqual(self.push_usernames(), {'fw'})
        self.assertIn('Bericht', self.push_payloads()[0]['body'])

    def test_task_reminder_independent_of_new_task_preference(self):
        from .send_email import send_aufgaben_email
        self.disable(self.fw_user, NotificationType.TASK_NEW, EMAIL, PUSH)
        send_aufgaben_email(self.user_aufgabe, self.org)
        self.assertEqual(self.mail_recipients(), {'fw@example.com'})


class ManualTaskReminderViewTests(NotificationTestBase):
    def setUp(self):
        super().setUp()
        aufgabe = Aufgabe2.objects.create(org=self.org, name='Bericht')
        self.user_aufgabe = UserAufgaben.objects.create(
            org=self.org, user=self.fw_user, aufgabe=aufgabe, faellig=timezone.localdate(),
        )
        self.client.force_login(self.org_user)
        self.reset_outgoing()

    def remind(self):
        return self.client.get(reverse('send_task_reminder'), {'id': self.user_aufgabe.id})

    def test_reminder_sent(self):
        self.assertEqual(self.remind().status_code, 200)
        self.assertEqual(self.mail_recipients(), {'fw@example.com'})
        self.assertEqual(self.push_usernames(), {'fw'})

    def test_push_only_user_can_still_be_reminded(self):
        self.mail_master_off(self.fw_user)
        self.assertEqual(self.remind().status_code, 200)
        self.smtp.assert_not_called()
        self.assertEqual(self.push_usernames(), {'fw'})

    def test_fully_opted_out_user_is_rejected(self):
        self.disable(self.fw_user, NotificationType.TASK_REMINDER, EMAIL, PUSH)
        response = self.remind()
        self.assertEqual(response.status_code, 400)
        self.smtp.assert_not_called()
        self.webpush.assert_not_called()


class AmpelReminderTests(NotificationTestBase):
    def setUp(self):
        super().setUp()
        self.config = AmpelConfiguration.objects.create(
            org=self.org, person_cluster=self.fw_cluster, enabled=True, message_text='Bitte melden',
        )
        self.reset_outgoing()

    def test_reminder_default(self):
        from .send_email import send_ampel_reminder
        send_ampel_reminder(self.fw_user, self.config)
        self.assertEqual(self.mail_recipients(), {'fw@example.com'})
        self.assertEqual(self.push_payloads()[0]['body'], 'Bitte melden')
        self.fw_user.customuser.refresh_from_db()
        self.assertEqual(self.fw_user.customuser.last_ampel_reminder, timezone.now().date())

    def test_reminder_respects_preferences(self):
        from .send_email import send_ampel_reminder
        self.disable(self.fw_user, NotificationType.AMPEL_REMINDER, PUSH)
        send_ampel_reminder(self.fresh(self.fw_user), self.config)
        self.assertEqual(self.mail_recipients(), {'fw@example.com'})
        self.webpush.assert_not_called()


class ChangeRequestDecisionTests(NotificationTestBase):
    def setUp(self):
        super().setUp()
        land = Einsatzland2.objects.create(org=self.org, name='Testland', code='TL')
        self.change_request = ChangeRequest.objects.create(
            org=self.org, change_type='einsatzland', object_id=land.id, status='approved',
            requested_by=self.team_user, reviewed_by=self.org_user, field_changes={},
        )
        self.reset_outgoing()

    def test_decision_reaches_requester(self):
        from .tasks import send_change_request_decision_email_task
        self.assertTrue(send_change_request_decision_email_task(self.change_request.id))
        self.assertEqual(self.mail_recipients(), {'team@example.com'})
        self.assertEqual(self.push_usernames(), {'team'})
        self.assertIn('genehmigt', self.push_payloads()[0]['body'])

    def test_decision_respects_preferences(self):
        from .tasks import send_change_request_decision_email_task
        self.disable(self.team_user, NotificationType.CHANGE_REQUEST_DECISION, EMAIL)
        send_change_request_decision_email_task(self.change_request.id)
        self.smtp.assert_not_called()
        self.assertEqual(self.push_usernames(), {'team'})

    def test_decision_is_queued_not_run(self):
        from .views_change_requests import _notify_requester_of_decision
        _notify_requester_of_decision(self.change_request)
        self.assertTrue(self.celery.called)
        self.smtp.assert_not_called()
        self.webpush.assert_not_called()


class TeamNotificationTests(NotificationTestBase):
    def setUp(self):
        super().setUp()
        self.land = Einsatzland2.objects.create(org=self.org, name='Testland', code='TL')
        other_land = Einsatzland2.objects.create(org=self.org, name='Anderes Land', code='AL')

        team, _ = Team.objects.get_or_create(user=self.team_user, defaults={'org': self.org})
        team.land.add(self.land)

        self.foreign_team_user = self.make_user('foreignteam', self.team_cluster)
        foreign_team, _ = Team.objects.get_or_create(user=self.foreign_team_user, defaults={'org': self.org})
        foreign_team.land.add(other_land)

        fw, _ = Freiwilliger.objects.get_or_create(user=self.fw_user, defaults={'org': self.org})
        fw.einsatzland2 = self.land
        fw.save()
        self.reset_outgoing()

    # -- Ampel ------------------------------------------------------------
    def send_ampel(self, status='R', comment='Hilfe'):
        from ORG.tasks import send_ampel_email_task
        ampel = Ampel2.objects.create(org=self.org, user=self.fw_user, status=status, comment=comment)
        self.reset_outgoing()
        return send_ampel_email_task(ampel.id)

    def test_team_ampel_gets_mail_and_push(self):
        self.send_ampel()
        self.assertEqual(self.mail_recipients(), {'org@example.com', 'team@example.com'})
        self.assertEqual(self.push_usernames(), {'team'})
        self.assertIn('Hilfe', self.push_payloads()[0]['body'])

    def test_team_ampel_respects_preferences(self):
        self.disable(self.team_user, NotificationType.TEAM_AMPEL_NEW, EMAIL, PUSH)
        self.send_ampel(status='G', comment='')
        self.assertEqual(self.mail_recipients(), {'org@example.com'})
        self.webpush.assert_not_called()

    def test_team_ampel_push_only(self):
        self.disable(self.team_user, NotificationType.TEAM_AMPEL_NEW, EMAIL)
        self.send_ampel()
        self.assertEqual(self.mail_recipients(), {'org@example.com'})
        self.assertEqual(self.push_usernames(), {'team'})

    def test_team_ampel_without_org_email_still_reaches_team(self):
        self.org.email = ''
        self.org.save()
        self.send_ampel()
        self.assertEqual(self.mail_recipients(), {'team@example.com'})

    # -- Aufgabe erledigt -------------------------------------------------
    def send_task_done(self, visible_by_team=True):
        from ORG.tasks import send_aufgabe_erledigt_email_task
        aufgabe = Aufgabe2.objects.create(org=self.org, name='Bericht', visible_by_team=visible_by_team)
        user_aufgabe = UserAufgaben.objects.create(
            org=self.org, user=self.fw_user, aufgabe=aufgabe, faellig=timezone.localdate(), erledigt=True,
        )
        self.reset_outgoing()
        return send_aufgabe_erledigt_email_task(user_aufgabe.id)

    def test_team_task_done_gets_mail_and_push(self):
        self.send_task_done()
        self.assertEqual(self.mail_recipients(), {'org@example.com', 'team@example.com'})
        self.assertEqual(self.push_usernames(), {'team'})

    def test_team_task_done_respects_preferences(self):
        self.disable(self.team_user, NotificationType.TEAM_TASK_DONE, PUSH)
        self.mail_master_off(self.team_user)
        self.send_task_done()
        self.assertEqual(self.mail_recipients(), {'org@example.com'})
        self.webpush.assert_not_called()

    def test_team_task_done_not_visible_for_team(self):
        self.send_task_done(visible_by_team=False)
        self.assertEqual(self.mail_recipients(), {'org@example.com'})
        self.webpush.assert_not_called()


class NotificationSettingsViewTests(NotificationTestBase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.fw_user)

    def post_pref(self, payload):
        return self.client.post(
            reverse('update_notification_preference'),
            data=json.dumps(payload) if not isinstance(payload, str) else payload,
            content_type='application/json',
        )

    def test_requires_login(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse('notification_settings')).status_code, 302)
        self.assertEqual(self.post_pref({'type': 'post', 'channel': 'email', 'enabled': False}).status_code, 302)

    def test_page_renders_visible_types_only(self):
        response = self.client.get(reverse('notification_settings'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-type="post"')
        self.assertContains(response, 'data-type="ampel_reminder"')
        self.assertNotContains(response, 'data-type="team_task_done"')
        self.assertNotContains(response, 'data-type="change_request_decision"')

    def test_page_reflects_saved_state(self):
        set_preference(self.fw_user, NotificationType.POST, PUSH, False)
        response = self.client.get(reverse('notification_settings'))
        groups = response.context['notification_groups']
        item = next(i for g in groups for i in g['items'] if i['type'] == 'post')
        self.assertTrue(item['email'])
        self.assertFalse(item['push'])

    def test_page_warns_when_mail_master_off_and_no_push_device(self):
        self.mail_master_off(self.fw_user)
        PushSubscription.objects.filter(user=self.fw_user).delete()
        response = self.client.get(reverse('notification_settings'))
        self.assertFalse(response.context['mail_master_enabled'])
        self.assertFalse(response.context['has_push_subscription'])

    def _push_inputs(self, response):
        return re.findall(r'<input[^>]*data-channel="push"[^>]*>', response.content.decode())

    def test_push_switches_disabled_and_off_without_push_device(self):
        PushSubscription.objects.filter(user=self.fw_user).delete()
        response = self.client.get(reverse('notification_settings'))
        inputs = self._push_inputs(response)
        self.assertTrue(inputs)
        for tag in inputs:
            self.assertIn('disabled', tag)
            self.assertNotIn('checked', tag)
        # Email switches stay usable
        self.assertNotIn('disabled', re.findall(r'<input[^>]*data-channel="email"[^>]*>', response.content.decode())[0])
        # Stored preference is not touched by the display
        self.assertTrue(get_channel_setting(self.fresh(self.fw_user), NotificationType.POST, PUSH))

    def test_push_switches_enabled_with_push_device(self):
        response = self.client.get(reverse('notification_settings'))
        for tag in self._push_inputs(response):
            self.assertNotIn('disabled', tag)
            self.assertIn('checked', tag)

    def test_page_lists_post_only_once(self):
        response = self.client.get(reverse('notification_settings'))
        self.assertEqual(response.content.decode().count('data-type="post"'), 2)  # email + push switch

    def test_page_is_translated_to_english(self):
        from django.utils import translation
        with translation.override('en'):
            response = self.client.get(reverse('notification_settings'), HTTP_ACCEPT_LANGUAGE='en')
        self.assertContains(response, 'New tasks')
        self.assertContains(response, 'When new tasks are assigned to you')
        self.assertNotContains(response, 'Neue Aufgaben')

    def test_update_preference(self):
        response = self.post_pref({'type': 'chat_direct', 'channel': 'push', 'enabled': False})
        self.assertEqual(response.status_code, 200)
        pref = NotificationPreference.objects.get(user=self.fw_user, notification_type='chat_direct')
        self.assertFalse(pref.push)
        self.assertTrue(pref.email)

    def test_update_rejects_invalid_payloads(self):
        for payload in [
            {'type': 'team_task_done', 'channel': 'email', 'enabled': False},  # not visible for FW
            {'type': 'unknown', 'channel': 'email', 'enabled': False},
            {'type': 'post', 'channel': 'sms', 'enabled': False},
            {'type': 'post', 'channel': 'email', 'enabled': 'no'},
            'not json',
        ]:
            with self.subTest(payload=payload):
                self.assertEqual(self.post_pref(payload).status_code, 400)
        self.assertFalse(NotificationPreference.objects.exists())

    def test_update_requires_post(self):
        self.assertEqual(self.client.get(reverse('update_notification_preference')).status_code, 405)

    def test_settings_page_links_to_notification_settings(self):
        response = self.client.get(reverse('settings'))
        self.assertContains(response, reverse('notification_settings'))


class UnsubscribeLinkTests(NotificationTestBase):
    def setUp(self):
        super().setUp()
        self.key = 'k' * 20
        self.fw_user.customuser.mail_notifications_unsubscribe_auth_key = self.key
        self.fw_user.customuser.save()

    def visit(self, query='', key=None):
        url = reverse('unsubscribe_mail_notifications', kwargs={'user_id': self.fw_user.id, 'auth_key': key or self.key})
        return self.client.get(url + query)

    def test_type_link_only_unsubscribes_that_type(self):
        self.visit('?type=post')
        user = self.fresh(self.fw_user)
        self.assertFalse(get_channel_setting(user, NotificationType.POST, EMAIL))
        self.assertTrue(get_channel_setting(user, NotificationType.POST, PUSH))
        self.assertTrue(get_channel_setting(user, NotificationType.CHAT_DIRECT, EMAIL))
        self.assertTrue(user.customuser.mail_notifications)

    def test_type_link_can_resubscribe(self):
        self.visit('?type=post')
        self.visit('?type=post&value=true')
        self.assertTrue(get_channel_setting(self.fresh(self.fw_user), NotificationType.POST, EMAIL))

    def test_link_without_type_switches_master_off(self):
        self.visit()
        user = self.fresh(self.fw_user)
        self.assertFalse(user.customuser.mail_notifications)
        self.assertFalse(NotificationPreference.objects.exists())

    def test_unknown_type_changes_nothing(self):
        self.visit('?type=nonsense')
        user = self.fresh(self.fw_user)
        self.assertTrue(user.customuser.mail_notifications)
        self.assertFalse(NotificationPreference.objects.exists())

    def test_wrong_key_changes_nothing(self):
        self.visit('?type=post', key='wrong-key')
        self.assertFalse(NotificationPreference.objects.exists())

    def test_one_click_post_unsubscribes_type_without_csrf(self):
        from django.test import Client
        url = reverse('unsubscribe_mail_notifications', kwargs={'user_id': self.fw_user.id, 'auth_key': self.key})
        response = Client(enforce_csrf_checks=True).post(
            url + '?type=post', {'List-Unsubscribe': 'One-Click'},
        )
        self.assertEqual(response.status_code, 200)
        user = self.fresh(self.fw_user)
        self.assertFalse(get_channel_setting(user, NotificationType.POST, EMAIL))
        self.assertTrue(user.customuser.mail_notifications)

    def test_one_click_post_without_type_switches_master_off(self):
        url = reverse('unsubscribe_mail_notifications', kwargs={'user_id': self.fw_user.id, 'auth_key': self.key})
        self.assertEqual(self.client.post(url).status_code, 200)
        self.assertFalse(self.fresh(self.fw_user).customuser.mail_notifications)

    def test_one_click_post_cannot_resubscribe(self):
        self.mail_master_off(self.fw_user)
        url = reverse('unsubscribe_mail_notifications', kwargs={'user_id': self.fw_user.id, 'auth_key': self.key})
        self.client.post(url + '?value=true')
        self.assertFalse(self.fresh(self.fw_user).customuser.mail_notifications)

    def test_one_click_post_needs_key_even_when_logged_in(self):
        self.client.force_login(self.fw_user)
        url = reverse('unsubscribe_mail_notifications', kwargs={'user_id': self.fw_user.id, 'auth_key': 'wrong-key'})
        self.assertEqual(self.client.post(url).status_code, 403)
        self.assertTrue(self.fresh(self.fw_user).customuser.mail_notifications)


class NotifyUserUnsubscribeHeaderTests(NotificationTestBase):
    def test_notify_user_passes_type_unsubscribe_url(self):
        notify_user(self.fresh(self.fw_user), NotificationType.POST, 'Betreff', email_html='<p>x</p>')
        url = self.smtp.call_args.kwargs['unsubscribe_url']
        self.assertEqual(url, get_type_unsubscribe_url(self.fresh(self.fw_user), NotificationType.POST))


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class OutgoingMailFormatTests(TestCase):
    """Real messages through the locmem backend: what spam filters will see."""

    def setUp(self):
        patch('Global.send_email.save_email_to_sent_folder').start()
        self.addCleanup(patch.stopall)

    def test_html_to_text_drops_css_and_keeps_links(self):
        from .send_email import html_to_text
        html = (
            '<html><head><style>p { color: red; }</style></head><body>'
            '<p>Hallo&nbsp;Max,</p><p>neue <b>Aufgabe</b>:<br>Bericht</p>'
            '<a href="https://example.com/x">Ansehen</a><!-- hidden --></body></html>'
        )
        text = html_to_text(html)
        self.assertNotIn('<', text)
        self.assertNotIn('color', text)
        self.assertNotIn('hidden', text)
        self.assertIn('Hallo Max,', text)
        self.assertIn('neue Aufgabe:\nBericht', text)
        self.assertIn('Ansehen (https://example.com/x)', text)

    def test_html_body_passed_as_text_is_converted(self):
        from .send_email import send_email_with_archive
        html = '<p>Hallo <b>Welt</b></p>'
        send_email_with_archive('S', html, 'from@example.com', ['to@example.com'], html_message=html)
        sent = mail.outbox[0]
        self.assertEqual(sent.body, 'Hallo Welt')
        self.assertEqual(sent.alternatives[0][0], html)

    def test_real_plain_text_is_kept(self):
        from .send_email import send_email_with_archive
        send_email_with_archive('S', 'Nur Text', 'from@example.com', ['to@example.com'], html_message='<p>Anders</p>')
        self.assertEqual(mail.outbox[0].body, 'Nur Text')

    def test_unsubscribe_headers(self):
        from .send_email import send_email_with_archive
        send_email_with_archive(
            'S', '', 'from@example.com', ['to@example.com'],
            html_message='<p>x</p>', unsubscribe_url='https://example.com/u?type=post',
        )
        message = mail.outbox[0].message()
        self.assertEqual(message['List-Unsubscribe'], '<https://example.com/u?type=post>')
        self.assertEqual(message['List-Unsubscribe-Post'], 'List-Unsubscribe=One-Click')

    def test_no_unsubscribe_headers_for_transactional_mail(self):
        from .send_email import send_email_with_archive
        send_email_with_archive('S', 'x', 'from@example.com', ['to@example.com'])
        self.assertIsNone(mail.outbox[0].message()['List-Unsubscribe'])
