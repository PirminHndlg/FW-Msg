from celery import shared_task
from chat.models import ChatGroup, ChatMessageDirect, ChatMessageGroup
from django.contrib.auth.models import User
from django.conf import settings
from django.urls import reverse
from Global.notifications import NotificationType, get_type_unsubscribe_url, notify_user
from Global.send_email import (
    format_chat_new_message_email,
    get_logo_url,
    get_org_color,
    user_display_name,
)

# Short badge for push when the chat row has an image (no inline image).
_IMAGE_NOTE_PLAIN = "📷 Bild"


def _message_has_image(msg):
    return bool(getattr(msg, "image", None) and getattr(msg.image, "name", None))


def _chat_push_body(sender_user: User, msg) -> str:
    text = (msg.message or "").strip()
    has_img = _message_has_image(msg)
    if has_img and text:
        return f"💬 {sender_user}: {text} · {_IMAGE_NOTE_PLAIN}"
    if has_img:
        return f"💬 {sender_user}: {_IMAGE_NOTE_PLAIN}"
    return f"💬 {sender_user}: {text}"


def _chat_email_context(*, org, recipient_user, sender_user, action_url, notification_type):
    return {
        'sender_name': user_display_name(sender_user),
        'action_url': action_url,
        'unsubscribe_url': get_type_unsubscribe_url(recipient_user, notification_type),
        'user_name': user_display_name(recipient_user),
        'org_name': org.name,
        'image_url': get_logo_url(org),
        'org_color': get_org_color(org),
    }


@shared_task
def notify_users_about_new_direct_chat_message(direct_message_id, sender_user_id):
    direct_message = ChatMessageDirect.objects.select_related('org', 'chat').get(id=direct_message_id)
    direct_chat = direct_message.chat
    sender_user = User.objects.get(id=sender_user_id)
    org = direct_message.org

    for recipient_user in direct_chat.users.exclude(pk=sender_user.pk):

        if direct_message.read:
            continue

        subject = f'Neue Nachricht von {str(sender_user)}'
        chat_url = f'{settings.DOMAIN_HOST}{reverse("chat_direct", args=[direct_chat.get_identifier()])}'
        email_html = format_chat_new_message_email(
            message_text=direct_message.message,
            has_image=_message_has_image(direct_message),
            group_name=None,
            **_chat_email_context(
                org=org,
                recipient_user=recipient_user,
                sender_user=sender_user,
                action_url=chat_url,
                notification_type=NotificationType.CHAT_DIRECT,
            ),
        )
        push_content = _chat_push_body(sender_user, direct_message)

        notify_user(
            recipient_user, NotificationType.CHAT_DIRECT, subject,
            email_html=email_html, push_body=push_content,
            url=reverse('chat_direct', args=[direct_chat.get_identifier()]),
            reply_to=[sender_user.email],
        )

    return True


@shared_task
def notify_users_about_new_group_chat_message(group_message_id, sender_user_id):
    group_message = ChatMessageGroup.objects.select_related('org', 'chat').get(id=group_message_id)
    sender_user = User.objects.get(id=sender_user_id)
    group_chat = group_message.chat
    org = group_message.org

    for recipient_user in group_chat.users.exclude(pk=sender_user.pk):

        if recipient_user in group_message.read_by.all():
            continue

        subject = f'Neue Nachricht in Gruppe {group_chat.name}'
        chat_url = f'{settings.DOMAIN_HOST}{reverse("chat_group", args=[group_chat.get_identifier()])}'
        email_html = format_chat_new_message_email(
            message_text=group_message.message,
            has_image=_message_has_image(group_message),
            group_name=group_chat.name,
            **_chat_email_context(
                org=org,
                recipient_user=recipient_user,
                sender_user=sender_user,
                action_url=chat_url,
                notification_type=NotificationType.CHAT_GROUP,
            ),
        )
        push_content = _chat_push_body(sender_user, group_message)

        notify_user(
            recipient_user, NotificationType.CHAT_GROUP, subject,
            email_html=email_html, push_body=push_content,
            url=reverse('chat_group', args=[group_chat.get_identifier()]),
            reply_to=[sender_user.email],
        )

    return True
