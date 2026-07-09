from celery import shared_task
from chat.models import ChatGroup, ChatMessageDirect, ChatMessageGroup
from django.contrib.auth.models import User
from django.conf import settings
from django.urls import reverse
from Global.push_notification import send_push_notification_to_user
from Global.send_email import (
    format_chat_new_group_invite_email,
    format_chat_new_message_email,
    get_logo_url,
    get_org_color,
    send_email_with_archive,
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


def _chat_email_context(*, org, recipient_user, sender_user, action_url):
    return {
        'sender_name': user_display_name(sender_user),
        'action_url': action_url,
        'unsubscribe_url': recipient_user.customuser.get_unsubscribe_url(),
        'user_name': user_display_name(recipient_user),
        'org_name': org.name,
        'image_url': get_logo_url(org),
        'org_color': get_org_color(org),
    }


@shared_task
def notify_users_about_new_group_chat(group_chat_id, sender_user_id):
    # Ignore for now
    return True
    group_chat = ChatGroup.objects.select_related('org').get(id=group_chat_id)
    sender_user = User.objects.get(id=sender_user_id)
    action_url = f'{settings.DOMAIN_HOST}{reverse("chat_group", args=[group_chat.get_identifier()])}'
    org = group_chat.org

    for recipient_user in group_chat.users.exclude(pk=sender_user.pk):
        subject = f'Neuer Gruppenchat: {group_chat.name}'
        push_content = f'Du wurdest zu einem neuen Gruppenchat eingeladen: {group_chat.name} von {str(sender_user)}'
        email_html = format_chat_new_group_invite_email(
            group_name=group_chat.name,
            **_chat_email_context(
                org=org,
                recipient_user=recipient_user,
                sender_user=sender_user,
                action_url=action_url,
            ),
        )

        if recipient_user.customuser.mail_notifications:
            send_email_with_archive(
                subject=subject,
                message='',
                from_email=settings.SERVER_EMAIL,
                recipient_list=[recipient_user.email],
                html_message=email_html,
                reply_to_list=[sender_user.email],
            )

        send_push_notification_to_user(
            user=recipient_user,
            title=subject,
            body=push_content,
            url=action_url,
        )

    return True


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
            ),
        )
        push_content = _chat_push_body(sender_user, direct_message)

        if recipient_user.customuser.mail_notifications:
            send_email_with_archive(
                subject=subject,
                message='',
                from_email=settings.SERVER_EMAIL,
                recipient_list=[recipient_user.email],
                html_message=email_html,
                reply_to_list=[sender_user.email],
            )

        send_push_notification_to_user(recipient_user, subject, push_content, url=reverse('chat_direct', args=[direct_chat.get_identifier()]))

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
            ),
        )
        push_content = _chat_push_body(sender_user, group_message)

        if recipient_user.customuser.mail_notifications:
            send_email_with_archive(
                subject=subject,
                message='',
                from_email=settings.SERVER_EMAIL,
                recipient_list=[recipient_user.email],
                html_message=email_html,
                reply_to_list=[sender_user.email],
            )

        send_push_notification_to_user(recipient_user, subject, push_content, url=reverse('chat_group', args=[group_chat.get_identifier()]))

    return True
