import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from .ampel_access import (
    _user_org_id,
    resolve_ampel_for_direct_reply,
    user_can_view_ampel_by_owner,
)
from .badge_utils import broadcast_unread_badge_for_user, get_unread_chat_message_count
from .models import ChatDirect, ChatGroup, ChatMessageDirect, ChatMessageGroup
from .tasks import notify_users_about_new_direct_chat_message, notify_users_about_new_group_chat_message


class ChatConsumer(AsyncWebsocketConsumer):
    """
    Single consumer for both direct and group chat rooms.

    URL kwargs (set by routing.py):
        chat_type  – "direct" or "group"
        identifier – the chat's hash identifier string
    """

    # ── lifecycle ────────────────────────────────────────────────────────────

    async def connect(self):
        self.user = self.scope["user"]

        # Reject unauthenticated WebSocket connections immediately.
        if not self.user.is_authenticated:
            await self.close(code=4001)
            return

        self.chat_type  = self.scope["url_route"]["kwargs"]["chat_type"]
        self.identifier = self.scope["url_route"]["kwargs"]["identifier"]

        # Verify membership in this org (same rules as HTTP chat views).
        chat_ctx = await self.resolve_chat_membership()
        if chat_ctx is None:
            await self.close(code=4003)
            return

        self.identifier, self.chat_pk = chat_ctx

        # channels_redis requires group names < 100 chars.
        # Identifier strings are long opaque hashes; truncate for Redis group-name limits.
        self.room_group = f"chat_{self.chat_type}_{self.identifier[:80]}"

        await self.channel_layer.group_add(self.room_group, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "room_group"):
            await self.channel_layer.group_discard(self.room_group, self.channel_name)

    # ── receive from browser ─────────────────────────────────────────────────

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except (json.JSONDecodeError, ValueError):
            return

        if data.get("action") == "edit":
            await self.handle_edit(data)
            return

        message_text = data.get("message", "").strip()
        if not message_text:
            return

        answer_to_ampel_id = data.get("answer_to_ampel_id")

        # Persist to DB and get back a serialisable dict.
        msg = await self.save_message(message_text, answer_to_ampel_id)

        # Broadcast to every client currently connected to this chat room.
        # Each receiver's chat_message() handler will mark the message as read.
        await self.channel_layer.group_send(self.room_group, {"type": "chat_message", **msg})

    async def handle_edit(self, data):
        message_id = data.get("message_id")
        message_text = data.get("message", "").strip()
        if not message_id or not message_text:
            return

        result = await self.edit_message(message_id, message_text)
        if result is None:
            return

        await self.channel_layer.group_send(
            self.room_group,
            {
                "type": "chat_message_edited",
                "id": result["id"],
                "message": result["message"],
            },
        )

    # ── receive from channel layer (i.e. broadcast from another consumer) ────

    async def chat_message(self, event):
        """Forward a group-sent message to this WebSocket client.

        If this client is a receiver (not the original sender), mark the
        message as read for them so unread counts stay accurate.
        """
        is_receiver = event["user_id"] != self.user.id
        if is_receiver:
            await self.mark_message_read(event["id"])
            await database_sync_to_async(broadcast_unread_badge_for_user)(self.user)

        payload = {
            "id":         event["id"],
            "message":    event["message"],
            "user":       event["user"],
            "user_id":    event["user_id"],
            "created_at": event["created_at"],
            "image_url":  event.get("image_url"),
        }
        if event.get("ampel") and user_can_view_ampel_by_owner(
            self.user,
            event.get("ampel_user_id"),
            _user_org_id(self.user),
        ):
            payload["ampel"] = event["ampel"]
        if event["user_id"] == self.user.id:
            payload["can_edit"] = event.get("can_edit", True)

        await self.send(text_data=json.dumps(payload))

    async def chat_message_edited(self, event):
        """Forward a message edit to this WebSocket client."""
        await self.send(
            text_data=json.dumps(
                {
                    "action": "edited",
                    "id": event["id"],
                    "message": event["message"],
                }
            )
        )

    # ── database helpers (sync → async) ─────────────────────────────────────

    @database_sync_to_async
    def mark_message_read(self, message_id):
        """Mark a single message as read for the current user (receiver).

        Scoped to ``self.chat_pk`` so we never touch rows from other chats,
        even if a bogus ``message_id`` appeared in an event.
        """
        if self.chat_type == "direct":
            ChatMessageDirect.objects.filter(
                id=message_id, chat_id=self.chat_pk
            ).update(read=True)
        else:
            try:
                msg = ChatMessageGroup.objects.get(id=message_id, chat_id=self.chat_pk)
                msg.read_by.add(self.user)
            except ChatMessageGroup.DoesNotExist:
                pass

    @database_sync_to_async
    def resolve_chat_membership(self):
        """Return (canonical_identifier, chat_pk) if the user may join this room; else None."""
        org = getattr(self.user, "org", None)
        if org is None:
            return None

        if self.chat_type == "direct":
            chat = (
                ChatDirect.objects.filter(
                    identifier=self.identifier,
                    users=self.user,
                    org=org,
                )
                .only("identifier", "pk")
                .first()
            )
        else:
            chat = (
                ChatGroup.objects.filter(
                    identifier=self.identifier,
                    users=self.user,
                    org=org,
                )
                .only("identifier", "pk")
                .first()
            )

        if chat is None:
            return None
        return (chat.identifier, chat.pk)

    @database_sync_to_async
    def edit_message(self, message_id, text):
        """Update a message if it belongs to this chat and was sent by the current user."""
        if self.chat_type == "direct":
            try:
                msg = ChatMessageDirect.objects.get(
                    id=message_id, chat_id=self.chat_pk, user=self.user
                )
            except ChatMessageDirect.DoesNotExist:
                return None
        else:
            try:
                msg = ChatMessageGroup.objects.get(
                    id=message_id, chat_id=self.chat_pk, user=self.user
                )
            except ChatMessageGroup.DoesNotExist:
                return None

        if not msg.can_be_edited():
            return None

        msg.message = text
        msg.is_edited = True
        msg.save(update_fields=["message", "is_edited", "updated_at"])
        return {"id": msg.id, "message": msg.message}

    @database_sync_to_async
    def save_message(self, text, answer_to_ampel_id=None):
        """Save the message to the database and return a serialisable dict."""
        org = self.user.customuser.org

        answer_to_ampel = None
        if self.chat_type == "direct":
            chat = ChatDirect.objects.get(pk=self.chat_pk, org=org)
            if answer_to_ampel_id:
                answer_to_ampel = resolve_ampel_for_direct_reply(
                    self.user, answer_to_ampel_id, chat
                )
            create_kw = {
                "org": org,
                "chat": chat,
                "user": self.user,
                "message": text,
            }
            if answer_to_ampel:
                create_kw["answer_to_ampel"] = answer_to_ampel
            msg = ChatMessageDirect.objects.create(**create_kw)
            notify_users_about_new_direct_chat_message.s(msg.id, self.user.id).apply_async(countdown=10)
        else:
            chat = ChatGroup.objects.get(pk=self.chat_pk, org=org)
            msg = ChatMessageGroup.objects.create(
                org=org, chat=chat, user=self.user, message=text
            )
            # Mark the message as read by the sender immediately.
            msg.mark_as_read_by(self.user)
            notify_users_about_new_group_chat_message.s(msg.id, self.user.id).apply_async(countdown=10)

        for recipient in chat.users.exclude(pk=self.user.pk):
            broadcast_unread_badge_for_user(recipient)

        image_url = msg.get_image_public_url()

        payload = {
            "id": msg.id,
            "message": msg.message,
            # str(user) uses the project's monkey-patched __str__
            # → get_full_name() or username
            "user": str(self.user),
            "user_id": self.user.id,
            "created_at": msg.created_at.strftime("%d.%m.%Y %H:%M"),
            "image_url": image_url,
            "can_edit": msg.can_be_edited(),
        }
        if answer_to_ampel:
            payload["ampel_user_id"] = answer_to_ampel.user_id
            payload["ampel"] = {
                "status": answer_to_ampel.status,
                "comment": answer_to_ampel.comment or "",
            }
        return payload


class ChatBadgeConsumer(AsyncWebsocketConsumer):
    """One connection per logged-in user; pushes global unread chat count."""

    async def connect(self):
        self.user = self.scope["user"]
        if not self.user.is_authenticated:
            await self.close(code=4001)
            return

        self.group_name = f"chat_user_{self.user.pk}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        n = await database_sync_to_async(get_unread_chat_message_count)(self.user)
        await self.send(
            text_data=json.dumps({"number_of_unread_messages": n})
        )

    async def disconnect(self, close_code):
        if getattr(self, "group_name", None):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def unread_badge(self, event):
        await self.send(
            text_data=json.dumps(
                {"number_of_unread_messages": event["number_of_unread_messages"]}
            )
        )
