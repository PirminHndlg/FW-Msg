import base64
import imaplib
import email
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate
from django.utils import timezone
from django.core.mail import get_connection, send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
import logging
from django.conf import settings
from django.urls import reverse

logger = logging.getLogger(__name__)

from .push_notification import send_push_notification_to_user


def save_email_to_sent_folder(subject, message, from_email, recipient_list, html_message=None, reply_to=None):
    """
    Save a copy of the sent email to the IMAP Sent folder.
    """
    try:
        # Get IMAP settings from Django settings
        imap_host = settings.IMAP_HOST
        imap_port = settings.IMAP_PORT
        imap_use_ssl = settings.IMAP_USE_SSL
        email_user = settings.EMAIL_HOST_USER
        email_password = settings.EMAIL_HOST_PASSWORD
        
        # Create email message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = from_email
        msg['To'] = ', '.join(recipient_list)
        if reply_to:
            msg['Reply-To'] = ', '.join(reply_to)
        msg['Date'] = formatdate(localtime=True)
        
        if message:
            text_part = MIMEText(message, 'plain', 'utf-8')
            msg.attach(text_part)
        
        if html_message:
            html_part = MIMEText(html_message, 'html', 'utf-8')
            msg.attach(html_part)
        
        # Connect to IMAP server
        if imap_use_ssl:
            imap = imaplib.IMAP4_SSL(str(imap_host), imap_port)
        else:
            imap = imaplib.IMAP4(str(imap_host), imap_port)
        
        # Login
        imap.login(str(email_user), str(email_password))
        
        # Append message to Sent folder
        sent_folder = 'Volunteer.Solutions'
        imap.append(sent_folder, '\\Seen', imaplib.Time2Internaldate(time.time()), msg.as_string().encode('utf-8'))
        
        # Logout
        imap.logout()
        
        print(f"Email archived to {sent_folder}")
        return True
        
    except Exception as e:
        print(f"Failed to archive email to IMAP Sent folder: {e}")
        logger.error(f"Failed to archive email to IMAP Sent folder: {e}")
        return False

def send_mail(
    subject,
    message,
    from_email,
    recipient_list,
    reply_to_list=None,
    fail_silently=False,
    auth_user=None,
    auth_password=None,
    connection=None,
    html_message=None,
):
    """
    Easy wrapper for sending a single message to a recipient list. All members
    of the recipient list will see the other recipients in the 'To' field.

    If from_email is None, use the DEFAULT_FROM_EMAIL setting.
    If auth_user is None, use the EMAIL_HOST_USER setting.
    If auth_password is None, use the EMAIL_HOST_PASSWORD setting.

    Note: The API for this method is frozen. New code wanting to extend the
    functionality should use the EmailMessage class directly.
    """
    connection = connection or get_connection(
        username=auth_user,
        password=auth_password,
        fail_silently=fail_silently,
    )
    mail = EmailMultiAlternatives(
        subject, message, from_email, recipient_list, connection=connection, reply_to=reply_to_list
    )
    if html_message:
        mail.attach_alternative(html_message, "text/html")

    return mail.send()


def send_email_with_archive(subject, message, from_email, recipient_list, html_message=None, reply_to_list=None, save_to_sent=True):
    """
    Enhanced email sending function that saves emails to IMAP Sent folder for archiving.
    This ensures sent emails appear in the mail server and external email programs.
    """
    try:
        # Send the email normally first
        result = send_mail(
            subject=subject,
            message=message,
            from_email=from_email,
            recipient_list=recipient_list,
            html_message=html_message,
            reply_to_list=reply_to_list
        )
        
        # If email was sent successfully and archiving is enabled, save to Sent folder
        if result and save_to_sent:
            save_email_to_sent_folder(
                subject=subject,
                message=message,
                from_email=from_email,
                recipient_list=recipient_list,
                html_message=html_message,
                reply_to=reply_to_list
                )
        
        return result
        
    except Exception as e:
        print(f"Email sending failed: {e}")
        return False

def format_aufgaben_email(aufgabe_name, aufgabe_deadline, base64_image, org_color, org_name, user_name, action_url, aufgabe_beschreibung='', unsubscribe_url=None):
    context = {
        'aufgabe_name': aufgabe_name,
        'aufgabe_beschreibung': aufgabe_beschreibung,
        'aufgabe_deadline': aufgabe_deadline.strftime('%d.%m.%Y') if aufgabe_deadline else '',
        'base64_image': base64_image,
        'org_color': org_color,
        'org_name': org_name,
        'user_name': user_name,
        'action_url': action_url,
        'unsubscribe_url': unsubscribe_url
    }
    return render_to_string('mail/task_reminder.html', context)

def format_birthday_reminder_email(birthday_user_name, user_email, birthday, org_name, base64_image, org_color, is_tomorrow=True):
    context = {
        'user_name': org_name,
        'birthday_user_name': birthday_user_name,
        'user_email': user_email,
        'birthday': birthday,
        'birthday_formatted': birthday.strftime('%d.%m.%Y') if birthday else '',
        'org_name': org_name,
        'base64_image': base64_image,
        'org_color': org_color,
        'is_tomorrow': is_tomorrow
    }
    return render_to_string('mail/birthday_reminder.html', context)

def format_new_aufgaben_email(aufgaben, base64_image, org_color, org_name, user_name, action_url, unsubscribe_url=None):
    aufgaben_name = ', '.join([aufgabe.aufgabe.name for aufgabe in aufgaben])
    context = {
        'aufgaben_name': aufgaben_name,
        'base64_image': base64_image,
        'org_name': org_name,
        'org_color': org_color,
        'user_name': user_name,
        'action_url': action_url,
        'unsubscribe_url': unsubscribe_url
    }
    return render_to_string('mail/new_tasks.html', context)

def format_aufgabe_erledigt_email(aufgabe_name, aufgabe_deadline, org_color, org_name, user_name, action_url, requires_confirmation=False, has_file_upload=False, aufgabe_beschreibung='', unsubscribe_url=None):
    # Convert boolean values to Yes/No text in German
    requires_confirmation_text = "Ja" if requires_confirmation else "Nein"
    has_file_upload_text = "Ja" if has_file_upload else "Nein"
    
    context = {
        'aufgabe_name': aufgabe_name,
        'aufgabe_beschreibung': aufgabe_beschreibung,
        'aufgabe_deadline': aufgabe_deadline.strftime('%d.%m.%Y') if aufgabe_deadline else '',
        'org_name': org_name,
        'org_color': org_color,
        'user_name': user_name,
        'requires_confirmation': requires_confirmation_text,
        'has_file_upload': has_file_upload_text,
        'unsubscribe_url': unsubscribe_url,
        'action_button': has_file_upload,
        'action_url': action_url
    }
    return render_to_string('mail/task_completed.html', context)

def format_register_email_fw(einmalpasswort, action_url, base64_image, org_color, org_name, user_name, username):
    context = {
        'einmalpasswort': einmalpasswort,
        'action_url': action_url,
        'base64_image': base64_image,
        'org_color': org_color,
        'org_name': org_name,
        'user_name': user_name,
        'username': username
    }
    return render_to_string('mail/register_volunteer.html', context)

def format_mail_calendar_reminder_email(title, start, end, location, description, action_url, unsubscribe_url, user_name, org_name, base64_image, org_color):
    event_name = title
    event_start = start.astimezone(timezone.get_current_timezone()).strftime('%d.%m.%Y %H:%M') if start else ''
    event_end = end.astimezone(timezone.get_current_timezone()).strftime('%d.%m.%Y %H:%M') if end else ''
    event_location = location if location else ''
    event_description = description if description else ''

    context = {
        'event_name': event_name,
        'event_start': event_start,
        'event_end': event_end,
        'event_location': event_location,
        'event_description': event_description,
        'action_url': action_url,
        'unsubscribe_url': unsubscribe_url,
        'base64_image': base64_image,
        'org_name': org_name,
        'org_color': org_color,
        'user_name': user_name
    }
    return render_to_string('mail/calendar_reminder.html', context)

def format_new_post_email(post_title, post_text, author_name, post_date, has_survey, action_url, unsubscribe_url, user_name, org_name, base64_image, org_color):
    """Format email for new post notifications"""
    # Format the post date
    formatted_date = post_date.astimezone(timezone.get_current_timezone()).strftime('%d.%m.%Y %H:%M') if post_date else ''
    
    # Truncate post text if it's too long for email
    max_length = 300
    truncated_text = post_text if len(post_text) <= max_length else post_text[:max_length] + '...'
    
    context = {
        'post_title': post_title,
        'post_text': truncated_text,
        'author_name': author_name,
        'post_date': formatted_date,
        'has_survey': has_survey,
        'action_url': action_url,
        'unsubscribe_url': unsubscribe_url,
        'user_name': user_name,
        'org_name': org_name,
        'base64_image': base64_image,
        'org_color': org_color
    }
    return render_to_string('mail/new_post.html', context)

def format_register_email_org(einmalpasswort, action_url, org_name, user_name, username, base64_image, org_color):
    context = {
        'base64_image': base64_image,
        'org_color': org_color,
        'einmalpasswort': einmalpasswort,
        'action_url': action_url,
        'org_name': org_name,
        'user_name': user_name,
        'username': username
    }
    return render_to_string('mail/register_organization.html', context)

def format_ampel_email(user_name, ampel_user_name, ampel_user_email, status, comment, ampel_date, action_url, unsubscribe_url, org_name, base64_image, org_color):
    """Format email for ampel status notifications to organization"""
    # Format the ampel date
    formatted_date = ampel_date.astimezone(timezone.get_current_timezone()).strftime('%d.%m.%Y %H:%M') if ampel_date else ''
    
    context = {
        'user_name': user_name,
        'ampel_user_name': ampel_user_name,
        'ampel_user_email': ampel_user_email,
        'status': status,
        'comment': comment,
        'ampel_date': formatted_date,
        'action_url': action_url,
        'unsubscribe_url': unsubscribe_url,
        'org_name': org_name,
        'base64_image': base64_image,
        'org_color': org_color
    }
    return render_to_string('mail/ampel_notification.html', context)

def format_image_uploaded_email(bild_titel, bild_beschreibung, uploader_name, image_count, action_url, unsubscribe_url, user_name, org_name, base64_image, org_color):
    """Format email for newly uploaded image notification to organization"""
    context = {
        'bild_titel': bild_titel,
        'bild_beschreibung': bild_beschreibung,
        'uploader_name': uploader_name,
        'image_count': image_count,
        'action_url': action_url,
        'unsubscribe_url': unsubscribe_url,
        'user_name': user_name,
        'org_name': org_name,
        'base64_image': base64_image,
        'org_color': org_color
    }
    return render_to_string('mail/image_uploaded.html', context)

def format_change_request_new_email(change_type, object_name, requester_name, reason, action_url, user_name, org_name, base64_image, org_color):
    """Format email for new change request notification to organization members"""
    context = {
        'change_type': change_type,
        'object_name': object_name,
        'requester_name': requester_name,
        'reason': reason,
        'action_url': action_url,
        'user_name': user_name,
        'org_name': org_name,
        'base64_image': base64_image,
        'org_color': org_color
    }
    return render_to_string('mail/change_request_new.html', context)

def format_change_request_decision_email(status, status_display, change_type, object_name, reviewer_name, review_comment, action_url, unsubscribe_url, user_name, org_name, base64_image, org_color):
    """Format email for change request decision notification to requester"""
    context = {
        'status': status,
        'status_display': status_display,
        'change_type': change_type,
        'object_name': object_name,
        'reviewer_name': reviewer_name,
        'review_comment': review_comment,
        'action_url': action_url,
        'unsubscribe_url': unsubscribe_url,
        'user_name': user_name,
        'org_name': org_name,
        'base64_image': base64_image,
        'org_color': org_color
    }
    return render_to_string('mail/change_request_decision.html', context)

def get_logo_base64(org):
    with open(org.logo.path, "rb") as org_logo:
        base64_image = base64.b64encode(org_logo.read()).decode('utf-8')
    return base64_image

def get_org_color(org):
    return org.farbe

def send_aufgaben_email(aufgabe, org):
    # Get the organization logo URL
    action_url = f'{settings.DOMAIN_HOST}{reverse("aufgaben_detail", args=[aufgabe.aufgabe.id])}'
    unsubscribe_url = aufgabe.user.customuser.get_unsubscribe_url()
    base64_image = get_logo_base64(org)
    org_color = get_org_color(org)
    aufg_name = aufgabe.aufgabe.name
    aufg_deadline = aufgabe.faellig
    aufg_beschreibung = aufgabe.aufgabe.beschreibung if aufgabe.aufgabe.beschreibung else ''
    user_name = f"{aufgabe.user.first_name} {aufgabe.user.last_name}"

    email_content = format_aufgaben_email(
        aufgabe_name=aufg_name,
        aufgabe_deadline=aufg_deadline,
        base64_image=base64_image,
        org_color=org_color,
        org_name=org.name,
        user_name=user_name,
        action_url=action_url,
        aufgabe_beschreibung=aufg_beschreibung,
        unsubscribe_url=unsubscribe_url
    )   

    subject = f'Erinnerung: {aufgabe.aufgabe.name}'

    faellig_text = ''
    if aufgabe.faellig:
        faellig_text = f'am {aufgabe.faellig.strftime("%d.%m.%Y")} '

    push_content = f'Die Aufgabe "{aufgabe.aufgabe.name}" ist {faellig_text}fällig.'

    send_push_notification_to_user(aufgabe.user, subject, push_content, url=action_url)

    if aufgabe.user.customuser.mail_notifications:
        send_email_with_archive(
            subject=subject,
            message=email_content,
            from_email=settings.SERVER_EMAIL,
            recipient_list=[aufgabe.user.email],
            html_message=email_content,
            reply_to_list=[org.email],
        )

    aufgabe.last_reminder = timezone.now()
    aufgabe.currently_sending = False
    aufgabe.save()

    return True

def send_new_aufgaben_email(aufgaben, org):
    action_url = f'{settings.DOMAIN_HOST}{reverse("aufgaben")}'

    base64_image = get_logo_base64(org)
    org_color = get_org_color(org)

    email_content = format_new_aufgaben_email(
        aufgaben=aufgaben,
        base64_image=base64_image,
        org_color=org_color,
        org_name=org.name,
        user_name=f"{aufgaben[0].user.first_name} {aufgaben[0].user.last_name}",
        action_url=action_url,
        unsubscribe_url=aufgaben[0].user.customuser.get_unsubscribe_url()
    )

    subject = f'Neue Aufgaben: {aufgaben[0].aufgabe.name}... und mehr'
        
    if aufgaben[0].user.customuser.mail_notifications and send_email_with_archive(subject, email_content, settings.SERVER_EMAIL, [aufgaben[0].user.email], html_message=email_content, reply_to_list=[org.email]):
        for aufgabe in aufgaben:
            aufgabe.last_reminder = timezone.now()
            aufgabe.currently_sending = False
            aufgabe.save()
        return True
    
    push_content = f'Neue Aufgaben: {aufgaben[0].aufgabe.name}... und mehr'
    send_push_notification_to_user(aufgaben[0].user, subject, push_content, url=action_url)
    
    for aufgabe in aufgaben:
        aufgabe.currently_sending = False
        aufgabe.save()
    
    return False

def send_new_post_email(post_id):
    from Global.models import Post2
    
    post = Post2.objects.get(id=post_id)
    org = post.org
    
    # Generate action URL for the post
    action_url = f'{settings.DOMAIN_HOST}{reverse("post_detail", args=[post.pk])}'
    
    # Get organization logo
    base64_image = get_logo_base64(org)
    org_color = get_org_color(org)
    
    # Get author information
    author_name = f"{post.user.first_name} {post.user.last_name}" if post.user.first_name and post.user.last_name else post.user.username
    
    # Email subject
    subject = f'Neuer Post: {post.title}'
    
    # Track successful sends
    successful_sends = 0
    
    for person_cluster in post.person_cluster.all():
        for user in person_cluster.get_users():
            # Skip if user already received this post
            if user in post.already_sent_to.all():
                continue
                
            # Skip if user doesn't want email notifications
            if hasattr(user, 'customuser') and not user.customuser.mail_notifications:
                continue
                
            # Get user's unsubscribe URL
            unsubscribe_url = user.customuser.get_unsubscribe_url() if hasattr(user, 'customuser') else None
            
            # Add user to already_sent_to list
            post.already_sent_to.add(user)
            
            # Format user name
            user_name = f"{user.first_name} {user.last_name}" if user.first_name and user.last_name else user.username
            
            # Generate email content
            email_content = format_new_post_email(
                post_title=post.title,
                post_text=post.text,
                author_name=author_name,
                post_date=post.date,
                has_survey=post.has_survey,
                action_url=action_url,
                unsubscribe_url=unsubscribe_url,
                user_name=user_name,
                org_name=org.name,
                base64_image=base64_image,
                org_color=org_color
            )
            
            # Send email using Django's send_mail
            if user.customuser.mail_notifications and send_email_with_archive(subject, '', settings.SERVER_EMAIL, [user.email], html_message=email_content):
                successful_sends += 1
                
            # Send push notification as well
            push_content = f'Neuer Post von {author_name}: {post.title}'
            if post.has_survey:
                push_content += ' (enthält Umfrage)'
                
            send_push_notification_to_user(user, subject, push_content, url=action_url)
    
    post.save()
    return successful_sends
