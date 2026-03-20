import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

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

        # Verify membership and fetch the chat pk in one query.
        # The group name uses the integer pk so it is always short and
        # contains only alphanumerics — the identifier hash is 128 chars
        # which exceeds the channels_redis 100-char limit.
        self.identifier = await self.get_identifier_if_member()
        if self.identifier is None:
            await self.close(code=4003)
            return

        # channels_redis requires group names < 100 chars.
        # The full identifier is 128 hex chars; truncate to 80 for the name
        # (prefix is 11-12 chars → total ≤ 92). Still effectively unique.
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

        message_text = data.get("message", "").strip()
        if not message_text:
            return

        # Persist to DB and get back a serialisable dict.
        msg = await self.save_message(message_text)

        # Broadcast to every client currently connected to this chat room.
        # Each receiver's chat_message() handler will mark the message as read.
        await self.channel_layer.group_send(self.room_group, {"type": "chat_message", **msg})

    # ── receive from channel layer (i.e. broadcast from another consumer) ────

    async def chat_message(self, event):
        """Forward a group-sent message to this WebSocket client.

        If this client is a receiver (not the original sender), mark the
        message as read for them so unread counts stay accurate.
        """
        is_receiver = event["user_id"] != self.user.id
        if is_receiver:
            await self.mark_message_read(event["id"])

        await self.send(
            text_data=json.dumps(
                {
                    "id":         event["id"],
                    "message":    event["message"],
                    "user":       event["user"],
                    "user_id":    event["user_id"],
                    "created_at": event["created_at"],
                }
            )
        )

    # ── database helpers (sync → async) ─────────────────────────────────────

    @database_sync_to_async
    def mark_message_read(self, message_id):
        """Mark a single message as read for the current user (receiver)."""
        if self.chat_type == "direct":
            ChatMessageDirect.objects.filter(id=message_id).update(read=True)
        else:
            try:
                msg = ChatMessageGroup.objects.get(id=message_id)
                msg.read_by.add(self.user)
            except ChatMessageGroup.DoesNotExist:
                pass

    @database_sync_to_async
    def get_identifier_if_member(self):
        """Return the chat pk if the user is a member, otherwise None."""
        if self.chat_type == "direct":
            chat = ChatDirect.objects.filter(
                identifier=self.identifier, users=self.user
            ).only("identifier").first()
        else:
            chat = ChatGroup.objects.filter(
                identifier=self.identifier, users=self.user
            ).only("identifier").first()
        return chat.identifier if chat else None

    @database_sync_to_async
    def save_message(self, text):
        """Save the message to the database and return a serialisable dict."""
        org = self.user.customuser.org

        if self.chat_type == "direct":
            chat = ChatDirect.objects.get(identifier=self.identifier)
            msg  = ChatMessageDirect.objects.create(
                org=org, chat=chat, user=self.user, message=text
            )
            notify_users_about_new_direct_chat_message.s(msg.id, self.user.id).apply_async(countdown=10)
        else:
            chat = ChatGroup.objects.get(identifier=self.identifier)
            msg  = ChatMessageGroup.objects.create(
                org=org, chat=chat, user=self.user, message=text
            )
            # Mark the message as read by the sender immediately.
            msg.mark_as_read_by(self.user)
            notify_users_about_new_group_chat_message.s(msg.id, self.user.id).apply_async(countdown=10)

        return {
            "id":         msg.id,
            "message":    msg.message,
            # str(user) uses the project's monkey-patched __str__
            # → get_full_name() or username
            "user":       str(self.user),
            "user_id":    self.user.id,
            "created_at": msg.created_at.strftime("%d.%m.%Y %H:%M"),
        }
