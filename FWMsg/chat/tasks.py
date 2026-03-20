from celery import shared_task
from chat.models import ChatGroup, ChatMessageDirect, ChatMessageGroup
from django.contrib.auth.models import User
from django.conf import settings
from django.urls import reverse
from Global.push_notification import send_push_notification_to_user
from Global.send_email import send_email_with_archive

@shared_task
def notify_users_about_new_group_chat(group_chat_id, sender_user_id):
    group_chat = ChatGroup.objects.get(id=group_chat_id)
    sender_user = User.objects.get(id=sender_user_id)
    
    for recipient_user in group_chat.users.exclude(pk=sender_user.pk):
        subject = f'Neuer Chat: {group_chat.name}'
        email_content = f'Du wurdest zu einem neuen Gruppenchat eingeladen: {group_chat.name} von {str(sender_user)}'
        push_content = f'Du wurdest zu einem neuen Gruppenchat eingeladen: {group_chat.name} von {str(sender_user)}'
        
        if recipient_user.customuser.mail_notifications:
            send_email_with_archive(
                    subject=subject,
                    message=email_content,
                    from_email=settings.SERVER_EMAIL,
                    recipient_list=[recipient_user.email],
                    html_message=email_content,
                    reply_to_list=[sender_user.email],
                )
        
        send_push_notification_to_user(
            user=recipient_user,
            title=subject,
            body=push_content,
            url=reverse('chat_group', args=[group_chat.get_identifier()])
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
        email_content = f'Du hast eine neue Nachricht von {str(sender_user)} erhalten: {direct_message.message}'
        push_content = f'💬 {str(sender_user)}: {direct_message.message}'
        
        if recipient_user.customuser.mail_notifications:
            send_email_with_archive(
                subject=subject,
                message=email_content,
                from_email=settings.SERVER_EMAIL,
                recipient_list=[recipient_user.email],
                html_message=email_content,
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
        
        subject = f'Neue Nachricht von {str(sender_user)}'
        email_content = f'Du hast eine neue Nachricht von {str(sender_user)} erhalten: {group_message.message}'
        push_content = f'💬 {str(sender_user)}: {group_message.message}'
        
        if recipient_user.customuser.mail_notifications:
            send_email_with_archive(
                subject=subject,
                message=email_content,
                from_email=settings.SERVER_EMAIL,
                recipient_list=[recipient_user.email],
                html_message=email_content,
                reply_to_list=[sender_user.email],
            )
        
        send_push_notification_to_user(recipient_user, subject, push_content, url=reverse('chat_group', args=[group_chat.get_identifier()]))
    
    return True