from celery import shared_task
from chat.models import ChatGroup, ChatMessageDirect, ChatMessageGroup
from django.contrib.auth.models import User
from django.conf import settings
from django.urls import reverse
from django.utils.html import escape
from Global.push_notification import send_push_notification_to_user
from Global.send_email import send_email_with_archive

# Short badge for mails/push when the chat row has an image (no inline image).
_IMAGE_NOTE_PLAIN = "📷 Bild"

_IMAGE_BADGE_HTML = (
    '<p style="margin:0 0 10px 0;">'
    '<span style="display:inline-block;background:#e7f5ff;color:#1864ab;'
    'font-size:12px;font-weight:600;padding:5px 12px;border-radius:999px;">'
    "📷 Bild</span>"
    "</p>"
)


def _message_has_image(msg):
    return bool(getattr(msg, "image", None) and getattr(msg.image, "name", None))


def _chat_email_message_html(msg):
    """Escaped HTML body: optional image badge + text (never embeds the file)."""
    parts = []
    if _message_has_image(msg):
        parts.append(_IMAGE_BADGE_HTML)
    text = (msg.message or "").strip()
    if text:
        parts.append(escape(text).replace("\n", "<br>\n"))
    return "".join(parts) if parts else "&nbsp;"


def _chat_email_plain_body(prefix: str, msg) -> str:
    """Plain-text body: prefix + optional 📷 note + message text."""
    bits = []
    if _message_has_image(msg):
        bits.append(_IMAGE_NOTE_PLAIN)
    text = (msg.message or "").strip()
    if text:
        bits.append(text)
    if bits:
        return prefix + ": " + " · ".join(bits)
    return prefix


def _chat_push_body(sender_user: User, msg) -> str:
    text = (msg.message or "").strip()
    has_img = _message_has_image(msg)
    if has_img and text:
        return f"💬 {sender_user}: {text} · {_IMAGE_NOTE_PLAIN}"
    if has_img:
        return f"💬 {sender_user}: {_IMAGE_NOTE_PLAIN}"
    return f"💬 {sender_user}: {text}"

email_template_new_group_chat = """<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0;padding:0;font-family:'Segoe UI',Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="padding:48px 16px;">
    <tr>
      <td align="center">
        <table width="100%" cellpadding="0" cellspacing="0"
               style="max-width:480px;">

          <!-- Sender name -->
          <tr>
            <td style="padding:0 0 8px 16px;">
              <span style="font-size:13px;font-weight:600;color:#555;">Du wurdest von {sender} zu einem neuen Gruppenchat eingeladen: {group_chat_name}</span>
            </td>
          </tr>

          <!-- CTA button -->
          <tr>
            <td align="center" style="padding:16px 0 0;">
              <a href="{url}"
                 style="display:inline-block;background:#1a1a1a;color:#ffffff;
                        text-decoration:none;font-size:14px;font-weight:600;
                        padding:11px 28px;border-radius:8px;letter-spacing:.2px;">
                Gruppenchat ansehen
              </a>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""


email_template_chat_message = """<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0;padding:0;font-family:'Segoe UI',Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="padding:48px 16px;">
    <tr>
      <td align="center">
        <table width="100%" cellpadding="0" cellspacing="0"
               style="max-width:480px;">

          <!-- Sender name -->
          <tr>
            <td style="padding:0 0 8px 16px;">
              <span style="font-size:13px;font-weight:600;color:#555;">{sender}</span>
            </td>
          </tr>

          <!-- Speech bubble (image = badge only, never inline image) -->
          <tr>
            <td style="background:#f1f3f5;border-radius:1.1rem;border-bottom-left-radius:0.25rem;
                       padding:16px 20px;
                       box-shadow:0 1px 4px rgba(0,0,0,.08);">
              <div style="margin:0;font-size:15px;line-height:1.6;color:#1a1a1a;">
                __MESSAGE_BODY__
              </div>
            </td>
          </tr>

          <!-- CTA button -->
          <tr>
            <td align="center" style="padding:32px 0 0;">
              <a href="{url}"
                 style="display:inline-block;background:#1a1a1a;color:#ffffff;
                        text-decoration:none;font-size:14px;font-weight:600;
                        padding:11px 28px;border-radius:8px;letter-spacing:.2px;">
                Zur Nachricht
              </a>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""

@shared_task
def notify_users_about_new_group_chat(group_chat_id, sender_user_id):
    group_chat = ChatGroup.objects.get(id=group_chat_id)
    sender_user = User.objects.get(id=sender_user_id)
    url = f'{settings.DOMAIN_HOST}{reverse("chat_group", args=[group_chat.get_identifier()])}'
    
    for recipient_user in group_chat.users.exclude(pk=sender_user.pk):
        subject = f'Neuer Gruppenchat: {group_chat.name}'
        email_content = f'Du wurdest zu einem neuen Gruppenchat eingeladen: {group_chat.name} von {str(sender_user)}'
        email_html = email_template_new_group_chat.format(
            sender=str(sender_user),
            group_chat_name=group_chat.name,
            url=url,
        )
        push_content = f'Du wurdest zu einem neuen Gruppenchat eingeladen: {group_chat.name} von {str(sender_user)}'
        
        if recipient_user.customuser.mail_notifications:
            send_email_with_archive(
                    subject=subject,
                    message=email_content,
                    from_email=settings.SERVER_EMAIL,
                    recipient_list=[recipient_user.email],
                    html_message=email_html,
                    reply_to_list=[sender_user.email],
                )
        
        send_push_notification_to_user(
            user=recipient_user,
            title=subject,
            body=push_content,
            url=url,
        )
    
    return True

@shared_task
def notify_users_about_new_direct_chat_message(direct_message_id, sender_user_id):
    direct_message = ChatMessageDirect.objects.get(id=direct_message_id)
    direct_chat = direct_message.chat
    sender_user = User.objects.get(id=sender_user_id)
    
    for recipient_user in direct_chat.users.exclude(pk=sender_user.pk):
        
        if direct_message.read:
            continue
        
        subject = f'Neue Nachricht von {str(sender_user)}'
        chat_url = f'{settings.DOMAIN_HOST}{reverse("chat_direct", args=[direct_chat.get_identifier()])}'
        email_content = _chat_email_plain_body(
            f"Du hast eine neue Nachricht von {sender_user} erhalten",
            direct_message,
        )
        email_html = email_template_chat_message.format(
            sender=str(sender_user),
            url=chat_url,
        ).replace("__MESSAGE_BODY__", _chat_email_message_html(direct_message))
        push_content = _chat_push_body(sender_user, direct_message)
        
        if recipient_user.customuser.mail_notifications:
            send_email_with_archive(
                subject=subject,
                message=email_content,
                from_email=settings.SERVER_EMAIL,
                recipient_list=[recipient_user.email],
                html_message=email_html,
                reply_to_list=[sender_user.email],
            )
        
        send_push_notification_to_user(recipient_user, subject, push_content, url=reverse('chat_direct', args=[direct_chat.get_identifier()]))
    
    return True

@shared_task
def notify_users_about_new_group_chat_message(group_message_id, sender_user_id):
    group_message = ChatMessageGroup.objects.get(id=group_message_id)
    sender_user = User.objects.get(id=sender_user_id)
    group_chat = group_message.chat
    
    for recipient_user in group_chat.users.exclude(pk=sender_user.pk):
        
        if recipient_user in group_message.read_by.all():
            continue
        
        subject = f'Neue Nachricht in Gruppe {group_chat.name}'
        chat_url = f'{settings.DOMAIN_HOST}{reverse("chat_group", args=[group_chat.get_identifier()])}'
        email_content = _chat_email_plain_body(
            f'Du hast eine neue Nachricht in der Gruppe „{group_chat.name}" von {sender_user} erhalten',
            group_message,
        )
        email_html = email_template_chat_message.format(
            sender=str(sender_user),
            url=chat_url,
        ).replace("__MESSAGE_BODY__", _chat_email_message_html(group_message))
        push_content = _chat_push_body(sender_user, group_message)
        
        if recipient_user.customuser.mail_notifications:
            send_email_with_archive(
                subject=subject,
                message=email_content,
                from_email=settings.SERVER_EMAIL,
                recipient_list=[recipient_user.email],
                html_message=email_html,
                reply_to_list=[sender_user.email],
            )
        
        send_push_notification_to_user(recipient_user, subject, push_content, url=reverse('chat_group', args=[group_chat.get_identifier()]))
    
    return True