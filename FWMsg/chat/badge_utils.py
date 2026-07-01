from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from .models import ChatMessageDirect, ChatMessageGroup


def get_unread_chat_message_count(user):
    """Total unread direct + group messages for this user (same rules as ajax_chat_poll)."""
    direct = (
        ChatMessageDirect.objects.filter(chat__users=user, read=False)
        .exclude(user=user)
        .count()
    )
    group = (
        ChatMessageGroup.objects.filter(chat__users=user)
        .exclude(read_by=user)
        .exclude(user=user)
        .count()
    )
    return direct + group


def broadcast_unread_badge_for_user(user):
    """Push current unread count to all badge WebSocket connections for this user."""
    n = get_unread_chat_message_count(user)
    layer = get_channel_layer()
    if layer is None:
        return
    async_to_sync(layer.group_send)(
        f"chat_user_{user.pk}",
        {"type": "unread.badge", "number_of_unread_messages": n},
    )


def broadcast_chat_message_to_room(chat_type, identifier, msg_dict):
    """Broadcast a saved chat message to all WebSocket clients in the room.

    chat_type: \"direct\" or \"group\"
    identifier: full chat identifier string (same truncation as ChatConsumer.room_group)
    msg_dict: keys id, message, user, user_id, created_at, image_url (opaque ``serve_chat_image`` URL).
    """
    layer = get_channel_layer()
    if layer is None:
        return
    room_group = f"chat_{chat_type}_{identifier[:80]}"
    async_to_sync(layer.group_send)(
        room_group,
        {"type": "chat_message", **msg_dict},
    )


def broadcast_chat_edit_to_room(chat_type, identifier, message_id, new_text):
    """Broadcast a message edit to all WebSocket clients in the room."""
    layer = get_channel_layer()
    if layer is None:
        return
    room_group = f"chat_{chat_type}_{identifier[:80]}"
    async_to_sync(layer.group_send)(
        room_group,
        {"type": "chat_message_edited", "id": message_id, "message": new_text},
    )
