"""
Tests for the chat app.

Coverage:
  - Models: __str__, get_identifier, get_last_message, mark_as_read / mark_as_read_by
  - Forms:  user queryset filtered by org
  - Views:  auth guard, chat_list, chat_direct, chat_group,
            create_chat_direct (incl. duplicate detection), create_chat_group,
            send_message_direct, send_message_group,
            ajax_chat_poll, ajax_chat_list_updates, ajax_chat_updates
"""

import json
from unittest.mock import patch, MagicMock

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from Global.models import CustomUser, PersonCluster
from ORG.models import Organisation

from .forms import ChatDirectForm, ChatGroupForm
from .models import ChatDirect, ChatGroup, ChatMessageDirect, ChatMessageGroup


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_org(name="Test Org"):
    return Organisation.objects.create(name=name, email=f"{name}@test.de")


def make_cluster(org, view="O"):
    return PersonCluster.objects.create(name="Cluster", org=org, view=view)


def make_user(org, username, cluster=None, password="pass1234"):
    user = User.objects.create_user(username=username, password=password)
    CustomUser.objects.create(user=user, org=org, person_cluster=cluster)
    return user


def make_direct_chat(org, *users):
    chat = ChatDirect.objects.create(org=org)
    for u in users:
        chat.users.add(u)
    return chat


def make_group_chat(org, name, *users):
    group = ChatGroup.objects.create(org=org, name=name)
    for u in users:
        group.users.add(u)
    return group


# Patch target for all Celery task calls dispatched inside views
_TASK_PATCH_TARGETS = [
    "chat.views.notify_users_about_new_direct_chat_message",
    "chat.views.notify_users_about_new_group_chat_message",
    "chat.views.notify_users_about_new_group_chat",
]


def patch_tasks(func):
    """Decorator that silences all Celery task dispatches."""
    for target in reversed(_TASK_PATCH_TARGETS):
        func = patch(target)(func)
    return func


# ---------------------------------------------------------------------------
# Base test case
# ---------------------------------------------------------------------------

class ChatBaseTest(TestCase):
    def setUp(self):
        self.org = make_org()
        self.cluster = make_cluster(self.org)
        self.alice = make_user(self.org, "alice", self.cluster)
        self.bob   = make_user(self.org, "bob",   self.cluster)
        self.carol = make_user(self.org, "carol", self.cluster)

        # Second org – used to verify cross-org isolation
        self.other_org = make_org("Other Org")
        self.other_cluster = make_cluster(self.other_org)
        self.dave = make_user(self.other_org, "dave", self.other_cluster)

        self.client = Client()

    def login(self, user, password="pass1234"):
        self.client.force_login(user)


# ===========================================================================
# Model tests
# ===========================================================================

class ChatDirectModelTest(ChatBaseTest):

    def test_str_returns_usernames(self):
        chat = make_direct_chat(self.org, self.alice, self.bob)
        names = str(chat)
        self.assertIn("alice", names)
        self.assertIn("bob", names)

    def test_get_identifier_generated_and_cached(self):
        chat = make_direct_chat(self.org, self.alice, self.bob)
        ident1 = chat.get_identifier()
        ident2 = chat.get_identifier()
        self.assertIsNotNone(ident1)
        self.assertEqual(ident1, ident2)

    def test_get_last_message_no_messages_returns_now(self):
        chat = make_direct_chat(self.org, self.alice, self.bob)
        before = timezone.now()
        result = chat.get_last_message()
        after = timezone.now()
        self.assertGreaterEqual(result, before)
        self.assertLessEqual(result, after)

    def test_get_last_message_with_messages(self):
        chat = make_direct_chat(self.org, self.alice, self.bob)
        msg = ChatMessageDirect.objects.create(
            chat=chat, user=self.alice, org=self.org, message="Hi"
        )
        self.assertEqual(chat.get_last_message(), msg.created_at)


class ChatGroupModelTest(ChatBaseTest):

    def test_str_returns_name(self):
        group = make_group_chat(self.org, "Test Group", self.alice, self.bob)
        self.assertEqual(str(group), "Test Group")

    def test_get_identifier_generated_and_cached(self):
        group = make_group_chat(self.org, "G", self.alice)
        ident = group.get_identifier()
        self.assertIsNotNone(ident)
        self.assertEqual(ident, group.get_identifier())

    def test_get_last_message_no_messages_returns_now(self):
        group = make_group_chat(self.org, "G", self.alice)
        before = timezone.now()
        result = group.get_last_message()
        after = timezone.now()
        self.assertGreaterEqual(result, before)
        self.assertLessEqual(result, after)


class ChatMessageDirectModelTest(ChatBaseTest):

    def test_mark_as_read(self):
        chat = make_direct_chat(self.org, self.alice, self.bob)
        msg = ChatMessageDirect.objects.create(
            chat=chat, user=self.alice, org=self.org, message="hello"
        )
        self.assertFalse(msg.read)
        msg.mark_as_read()
        msg.refresh_from_db()
        self.assertTrue(msg.read)

    def test_str_returns_message_text(self):
        chat = make_direct_chat(self.org, self.alice, self.bob)
        msg = ChatMessageDirect.objects.create(
            chat=chat, user=self.alice, org=self.org, message="test message"
        )
        self.assertEqual(str(msg), "test message")


class ChatMessageGroupModelTest(ChatBaseTest):

    def test_mark_as_read_by(self):
        group = make_group_chat(self.org, "G", self.alice, self.bob)
        msg = ChatMessageGroup.objects.create(
            chat=group, user=self.alice, org=self.org, message="hey"
        )
        self.assertFalse(msg.read_by.filter(pk=self.bob.pk).exists())
        msg.mark_as_read_by(self.bob)
        self.assertTrue(msg.read_by.filter(pk=self.bob.pk).exists())

    def test_str_returns_message_text(self):
        group = make_group_chat(self.org, "G", self.alice)
        msg = ChatMessageGroup.objects.create(
            chat=group, user=self.alice, org=self.org, message="greetings"
        )
        self.assertEqual(str(msg), "greetings")


# ===========================================================================
# Form tests
# ===========================================================================

class ChatDirectFormTest(ChatBaseTest):

    def test_users_queryset_filtered_to_org(self):
        form = ChatDirectForm(org=self.org, current_user=self.alice)
        qs = form.fields["users"].queryset
        self.assertIn(self.bob, qs)
        self.assertNotIn(self.dave, qs)   # different org

    def test_current_user_excluded(self):
        form = ChatDirectForm(org=self.org, current_user=self.alice)
        self.assertNotIn(self.alice, form.fields["users"].queryset)


class ChatGroupFormTest(ChatBaseTest):

    def test_users_queryset_filtered_to_org(self):
        form = ChatGroupForm(org=self.org, current_user=self.alice)
        qs = form.fields["users"].queryset
        self.assertIn(self.bob, qs)
        self.assertNotIn(self.dave, qs)

    def test_current_user_excluded(self):
        form = ChatGroupForm(org=self.org, current_user=self.alice)
        self.assertNotIn(self.alice, form.fields["users"].queryset)


# ===========================================================================
# Auth guard tests
# ===========================================================================

class AuthGuardTest(TestCase):
    """All chat URLs must redirect unauthenticated users to the login page."""

    ANON_URLS = [
        ("chat_list", []),
        ("create_chat_direct", []),
        ("create_chat_group", []),
        ("ajax_chat_poll", []),
        ("ajax_chat_list_updates", []),
    ]

    def test_unauthenticated_redirected(self):
        client = Client()
        for name, args in self.ANON_URLS:
            with self.subTest(url=name):
                response = client.get(reverse(name, args=args))
                self.assertIn(response.status_code, [302, 301], msg=name)


# ===========================================================================
# View: chat_list
# ===========================================================================

class ChatListViewTest(ChatBaseTest):

    def test_renders_for_logged_in_user(self):
        self.login(self.alice)
        response = self.client.get(reverse("chat_list"))
        self.assertEqual(response.status_code, 200)

    def test_shows_own_direct_chat(self):
        chat = make_direct_chat(self.org, self.alice, self.bob)
        chat.get_identifier()
        self.login(self.alice)
        response = self.client.get(reverse("chat_list"))
        conversations = response.context["conversations"]
        ids = [c["id"] for c in conversations]
        self.assertIn(chat.identifier, ids)

    def test_does_not_show_other_users_chat(self):
        chat = make_direct_chat(self.org, self.bob, self.carol)
        chat.get_identifier()
        self.login(self.alice)
        response = self.client.get(reverse("chat_list"))
        conversations = response.context["conversations"]
        ids = [c["id"] for c in conversations]
        self.assertNotIn(chat.identifier, ids)

    def test_unread_count_in_context(self):
        chat = make_direct_chat(self.org, self.alice, self.bob)
        ChatMessageDirect.objects.create(
            chat=chat, user=self.bob, org=self.org, message="unread"
        )
        self.login(self.alice)
        response = self.client.get(reverse("chat_list"))
        conv = next(
            c for c in response.context["conversations"] if c["type"] == "direct"
        )
        self.assertEqual(conv["unread_count"], 1)

    def test_group_chat_visible(self):
        group = make_group_chat(self.org, "MyGroup", self.alice, self.bob)
        group.get_identifier()
        self.login(self.alice)
        response = self.client.get(reverse("chat_list"))
        conversations = response.context["conversations"]
        group_ids = [c["id"] for c in conversations if c["type"] == "group"]
        self.assertIn(group.identifier, group_ids)


# ===========================================================================
# View: chat_direct
# ===========================================================================

class ChatDirectViewTest(ChatBaseTest):

    def setUp(self):
        super().setUp()
        self.chat = make_direct_chat(self.org, self.alice, self.bob)
        self.ident = self.chat.get_identifier()

    def test_get_renders_chat(self):
        self.login(self.alice)
        response = self.client.get(reverse("chat_direct", args=[self.ident]))
        self.assertEqual(response.status_code, 200)
        self.assertIn("chat_messages", response.context)

    def test_messages_marked_as_read_on_get(self):
        msg = ChatMessageDirect.objects.create(
            chat=self.chat, user=self.bob, org=self.org, message="hi"
        )
        self.assertFalse(msg.read)
        self.login(self.alice)
        self.client.get(reverse("chat_direct", args=[self.ident]))
        msg.refresh_from_db()
        self.assertTrue(msg.read)

    @patch_tasks
    def test_post_creates_message(self, *mocks):
        self.login(self.alice)
        self.client.post(
            reverse("chat_direct", args=[self.ident]),
            {"message": "Hello Bob"},
        )
        self.assertTrue(
            ChatMessageDirect.objects.filter(
                chat=self.chat, user=self.alice, message="Hello Bob"
            ).exists()
        )

    @patch_tasks
    def test_post_redirects_back_to_chat(self, *mocks):
        self.login(self.alice)
        response = self.client.post(
            reverse("chat_direct", args=[self.ident]),
            {"message": "Hey"},
        )
        self.assertRedirects(
            response, reverse("chat_direct", args=[self.ident]),
            fetch_redirect_response=False,
        )

    def test_non_member_redirected_to_list(self):
        self.login(self.carol)
        response = self.client.get(reverse("chat_direct", args=[self.ident]))
        self.assertRedirects(
            response, reverse("chat_list"), fetch_redirect_response=False
        )

    def test_other_org_user_redirected(self):
        self.login(self.dave)
        response = self.client.get(reverse("chat_direct", args=[self.ident]))
        self.assertRedirects(
            response, reverse("chat_list"), fetch_redirect_response=False
        )


# ===========================================================================
# View: chat_group
# ===========================================================================

class ChatGroupViewTest(ChatBaseTest):

    def setUp(self):
        super().setUp()
        self.group = make_group_chat(self.org, "Dev", self.alice, self.bob)
        self.ident = self.group.get_identifier()

    def test_get_renders_group(self):
        self.login(self.alice)
        response = self.client.get(reverse("chat_group", args=[self.ident]))
        self.assertEqual(response.status_code, 200)

    def test_messages_marked_as_read_on_get(self):
        msg = ChatMessageGroup.objects.create(
            chat=self.group, user=self.bob, org=self.org, message="yo"
        )
        self.login(self.alice)
        self.client.get(reverse("chat_group", args=[self.ident]))
        self.assertTrue(msg.read_by.filter(pk=self.alice.pk).exists())

    @patch_tasks
    def test_post_creates_group_message(self, *mocks):
        self.login(self.alice)
        self.client.post(
            reverse("chat_group", args=[self.ident]),
            {"message": "Group hello"},
        )
        self.assertTrue(
            ChatMessageGroup.objects.filter(
                chat=self.group, user=self.alice, message="Group hello"
            ).exists()
        )

    @patch_tasks
    def test_sender_marked_as_read_after_post(self, *mocks):
        self.login(self.alice)
        self.client.post(
            reverse("chat_group", args=[self.ident]),
            {"message": "Self-read check"},
        )
        msg = ChatMessageGroup.objects.get(chat=self.group, message="Self-read check")
        self.assertTrue(msg.read_by.filter(pk=self.alice.pk).exists())

    def test_non_member_redirected(self):
        self.login(self.carol)
        response = self.client.get(reverse("chat_group", args=[self.ident]))
        self.assertRedirects(
            response, reverse("chat_list"), fetch_redirect_response=False
        )


# ===========================================================================
# View: create_chat_direct
# ===========================================================================

class CreateChatDirectViewTest(ChatBaseTest):

    def test_get_renders_form(self):
        self.login(self.alice)
        response = self.client.get(reverse("create_chat_direct"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("form", response.context)
        self.assertIn("available_users", response.context)

    @patch_tasks
    def test_post_creates_new_chat(self, *mocks):
        self.login(self.alice)
        self.client.post(
            reverse("create_chat_direct"), {"users": [self.bob.pk]}
        )
        self.assertTrue(
            ChatDirect.objects.filter(
                org=self.org, users=self.alice
            ).filter(users=self.bob).exists()
        )

    @patch_tasks
    def test_post_redirects_to_existing_chat(self, *mocks):
        existing = make_direct_chat(self.org, self.alice, self.bob)
        ident = existing.get_identifier()
        self.login(self.alice)
        response = self.client.post(
            reverse("create_chat_direct"), {"users": [self.bob.pk]}
        )
        self.assertRedirects(
            response,
            reverse("chat_direct", args=[ident]),
            fetch_redirect_response=False,
        )
        # No duplicate chat created
        count = (
            ChatDirect.objects.filter(org=self.org, users=self.alice)
            .filter(users=self.bob)
            .count()
        )
        self.assertEqual(count, 1)

    def test_available_users_excludes_current_user(self):
        self.login(self.alice)
        response = self.client.get(reverse("create_chat_direct"))
        available = list(response.context["available_users"])
        self.assertNotIn(self.alice, available)

    def test_available_users_excludes_other_org(self):
        self.login(self.alice)
        response = self.client.get(reverse("create_chat_direct"))
        available = list(response.context["available_users"])
        self.assertNotIn(self.dave, available)


# ===========================================================================
# View: create_chat_group
# ===========================================================================

class CreateChatGroupViewTest(ChatBaseTest):

    def test_get_renders_form(self):
        self.login(self.alice)
        response = self.client.get(reverse("create_chat_group"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("form", response.context)

    @patch_tasks
    def test_post_creates_group(self, *mocks):
        self.login(self.alice)
        self.client.post(
            reverse("create_chat_group"),
            {"name": "New Group", "description": "", "users": [self.bob.pk]},
        )
        self.assertTrue(
            ChatGroup.objects.filter(org=self.org, name="New Group").exists()
        )

    @patch_tasks
    def test_creator_added_as_member(self, *mocks):
        self.login(self.alice)
        self.client.post(
            reverse("create_chat_group"),
            {"name": "Crew", "description": "", "users": [self.bob.pk]},
        )
        group = ChatGroup.objects.get(org=self.org, name="Crew")
        self.assertIn(self.alice, group.users.all())

    @patch_tasks
    def test_post_redirects_to_group(self, *mocks):
        self.login(self.alice)
        response = self.client.post(
            reverse("create_chat_group"),
            {"name": "Redirect Group", "description": "", "users": [self.bob.pk]},
        )
        group = ChatGroup.objects.get(org=self.org, name="Redirect Group")
        self.assertRedirects(
            response,
            reverse("chat_group", args=[group.get_identifier()]),
            fetch_redirect_response=False,
        )


# ===========================================================================
# View: send_message_direct (AJAX)
# ===========================================================================

class SendMessageDirectViewTest(ChatBaseTest):

    def setUp(self):
        super().setUp()
        self.chat = make_direct_chat(self.org, self.alice, self.bob)
        self.ident = self.chat.get_identifier()
        self.url = reverse("send_message_direct", args=[self.ident])

    @patch_tasks
    def test_post_json_creates_message_and_returns_json(self, *mocks):
        self.login(self.alice)
        response = self.client.post(
            self.url,
            data=json.dumps({"message": "Hello via AJAX"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("id", data)
        self.assertEqual(data["message"], "Hello via AJAX")
        self.assertIn("created_at", data)

    @patch_tasks
    def test_response_contains_user_str(self, *mocks):
        self.alice.first_name = "Alice"
        self.alice.last_name = "Smith"
        self.alice.save()
        self.login(self.alice)
        response = self.client.post(
            self.url,
            data=json.dumps({"message": "Test"}),
            content_type="application/json",
        )
        self.assertEqual(response.json()["user"], "Alice Smith")

    def test_empty_message_returns_400(self):
        self.login(self.alice)
        response = self.client.post(
            self.url,
            data=json.dumps({"message": "   "}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_non_member_returns_404(self):
        self.login(self.carol)
        response = self.client.post(
            self.url,
            data=json.dumps({"message": "Hi"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 404)

    def test_get_method_not_allowed(self):
        self.login(self.alice)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)


# ===========================================================================
# View: send_message_group (AJAX)
# ===========================================================================

class SendMessageGroupViewTest(ChatBaseTest):

    def setUp(self):
        super().setUp()
        self.group = make_group_chat(self.org, "G", self.alice, self.bob)
        self.ident = self.group.get_identifier()
        self.url = reverse("send_message_group", args=[self.ident])

    @patch_tasks
    def test_post_creates_message(self, *mocks):
        self.login(self.alice)
        response = self.client.post(
            self.url,
            data=json.dumps({"message": "Group AJAX"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            ChatMessageGroup.objects.filter(
                chat=self.group, user=self.alice, message="Group AJAX"
            ).exists()
        )

    @patch_tasks
    def test_sender_auto_read(self, *mocks):
        self.login(self.alice)
        self.client.post(
            self.url,
            data=json.dumps({"message": "Auto read"}),
            content_type="application/json",
        )
        msg = ChatMessageGroup.objects.get(chat=self.group, message="Auto read")
        self.assertTrue(msg.read_by.filter(pk=self.alice.pk).exists())

    def test_empty_message_returns_400(self):
        self.login(self.alice)
        response = self.client.post(
            self.url,
            data=json.dumps({"message": ""}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_non_member_returns_404(self):
        self.login(self.carol)
        response = self.client.post(
            self.url,
            data=json.dumps({"message": "Sneak"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 404)


# ===========================================================================
# View: ajax_chat_poll
# ===========================================================================

class AjaxChatPollViewTest(ChatBaseTest):

    def test_returns_zero_when_no_messages(self):
        self.login(self.alice)
        response = self.client.get(reverse("ajax_chat_poll"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["number_of_unread_messages"], 0)

    def test_counts_unread_direct_messages(self):
        chat = make_direct_chat(self.org, self.alice, self.bob)
        ChatMessageDirect.objects.create(
            chat=chat, user=self.bob, org=self.org, message="unread"
        )
        self.login(self.alice)
        data = self.client.get(reverse("ajax_chat_poll")).json()
        self.assertEqual(data["number_of_unread_messages"], 1)

    def test_own_messages_not_counted(self):
        chat = make_direct_chat(self.org, self.alice, self.bob)
        ChatMessageDirect.objects.create(
            chat=chat, user=self.alice, org=self.org, message="own"
        )
        self.login(self.alice)
        data = self.client.get(reverse("ajax_chat_poll")).json()
        self.assertEqual(data["number_of_unread_messages"], 0)

    def test_counts_unread_group_messages(self):
        group = make_group_chat(self.org, "G", self.alice, self.bob)
        ChatMessageGroup.objects.create(
            chat=group, user=self.bob, org=self.org, message="group unread"
        )
        self.login(self.alice)
        data = self.client.get(reverse("ajax_chat_poll")).json()
        self.assertEqual(data["number_of_unread_messages"], 1)

    def test_read_group_messages_not_counted(self):
        group = make_group_chat(self.org, "G", self.alice, self.bob)
        msg = ChatMessageGroup.objects.create(
            chat=group, user=self.bob, org=self.org, message="already read"
        )
        msg.mark_as_read_by(self.alice)
        self.login(self.alice)
        data = self.client.get(reverse("ajax_chat_poll")).json()
        self.assertEqual(data["number_of_unread_messages"], 0)


# ===========================================================================
# View: ajax_chat_list_updates
# ===========================================================================

class AjaxChatListUpdatesViewTest(ChatBaseTest):

    def test_returns_conversation_list(self):
        chat = make_direct_chat(self.org, self.alice, self.bob)
        chat.get_identifier()
        self.login(self.alice)
        data = self.client.get(reverse("ajax_chat_list_updates")).json()
        self.assertIn("conversations", data)
        self.assertTrue(any(c["id"] == chat.identifier for c in data["conversations"]))

    def test_unread_count_correct(self):
        chat = make_direct_chat(self.org, self.alice, self.bob)
        ident = chat.get_identifier()  # ensure identifier is generated & saved
        ChatMessageDirect.objects.create(
            chat=chat, user=self.bob, org=self.org, message="hi"
        )
        self.login(self.alice)
        data = self.client.get(reverse("ajax_chat_list_updates")).json()
        conv = next(c for c in data["conversations"] if c["id"] == ident)
        self.assertEqual(conv["unread_count"], 1)

    def test_other_users_chats_not_returned(self):
        chat = make_direct_chat(self.org, self.bob, self.carol)
        chat.get_identifier()
        self.login(self.alice)
        data = self.client.get(reverse("ajax_chat_list_updates")).json()
        ids = [c["id"] for c in data["conversations"]]
        self.assertNotIn(chat.identifier, ids)


# ===========================================================================
# View: ajax_chat_updates
# ===========================================================================

class AjaxChatUpdatesViewTest(ChatBaseTest):

    def setUp(self):
        super().setUp()
        self.chat = make_direct_chat(self.org, self.alice, self.bob)
        self.ident = self.chat.get_identifier()
        self.group = make_group_chat(self.org, "G", self.alice, self.bob)
        self.gident = self.group.get_identifier()

    def _updates_url(self, chat_type, chat_id, last_id=0):
        base = reverse("ajax_chat_updates", args=[chat_type, chat_id])
        return f"{base}?last_id={last_id}"

    def test_returns_new_direct_messages(self):
        msg = ChatMessageDirect.objects.create(
            chat=self.chat, user=self.bob, org=self.org, message="new"
        )
        self.login(self.alice)
        data = self.client.get(self._updates_url("direct", self.ident, 0)).json()
        self.assertEqual(len(data["messages"]), 1)
        self.assertEqual(data["messages"][0]["id"], msg.id)

    def test_last_id_filters_already_seen_messages(self):
        msg1 = ChatMessageDirect.objects.create(
            chat=self.chat, user=self.bob, org=self.org, message="old"
        )
        msg2 = ChatMessageDirect.objects.create(
            chat=self.chat, user=self.bob, org=self.org, message="new"
        )
        self.login(self.alice)
        data = self.client.get(
            self._updates_url("direct", self.ident, msg1.id)
        ).json()
        ids = [m["id"] for m in data["messages"]]
        self.assertNotIn(msg1.id, ids)
        self.assertIn(msg2.id, ids)

    def test_direct_messages_marked_as_read(self):
        msg = ChatMessageDirect.objects.create(
            chat=self.chat, user=self.bob, org=self.org, message="mark me"
        )
        self.assertFalse(msg.read)
        self.login(self.alice)
        self.client.get(self._updates_url("direct", self.ident, 0))
        msg.refresh_from_db()
        self.assertTrue(msg.read)

    def test_returns_new_group_messages(self):
        msg = ChatMessageGroup.objects.create(
            chat=self.group, user=self.bob, org=self.org, message="group new"
        )
        self.login(self.alice)
        data = self.client.get(self._updates_url("group", self.gident, 0)).json()
        ids = [m["id"] for m in data["messages"]]
        self.assertIn(msg.id, ids)

    def test_group_messages_marked_as_read(self):
        msg = ChatMessageGroup.objects.create(
            chat=self.group, user=self.bob, org=self.org, message="read me"
        )
        self.login(self.alice)
        self.client.get(self._updates_url("group", self.gident, 0))
        self.assertTrue(msg.read_by.filter(pk=self.alice.pk).exists())

    def test_invalid_chat_type_returns_400(self):
        self.login(self.alice)
        response = self.client.get(self._updates_url("unknown", self.ident, 0))
        self.assertEqual(response.status_code, 400)

    def test_non_member_returns_404(self):
        self.login(self.carol)
        response = self.client.get(self._updates_url("direct", self.ident, 0))
        self.assertEqual(response.status_code, 404)

    def test_message_payload_fields(self):
        ChatMessageDirect.objects.create(
            chat=self.chat, user=self.bob, org=self.org, message="payload"
        )
        self.login(self.alice)
        data = self.client.get(self._updates_url("direct", self.ident, 0)).json()
        msg = data["messages"][0]
        for field in ("id", "user", "user_id", "message", "created_at"):
            self.assertIn(field, msg)
