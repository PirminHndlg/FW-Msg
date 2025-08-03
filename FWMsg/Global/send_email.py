import base64
import imaplib
import email
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate
from django.utils import timezone
from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings

from .push_notification import send_push_notification_to_user


def save_email_to_sent_folder(subject, message, from_email, recipient_list, html_message=None):
    """
    Save a copy of the sent email to the IMAP Sent folder.
    """
    try:
        # Get IMAP settings from Django settings
        imap_host = getattr(settings, 'IMAP_HOST', None)
        imap_port = getattr(settings, 'IMAP_PORT', 993)
        imap_use_ssl = getattr(settings, 'IMAP_USE_SSL', True)
        email_user = getattr(settings, 'EMAIL_HOST_USER', None)
        email_password = getattr(settings, 'EMAIL_HOST_PASSWORD', None)
        
        if not all([imap_host, email_user, email_password]):
            print("IMAP settings not configured, skipping email archiving")
            return False
        
        # Create email message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = from_email
        msg['To'] = ', '.join(recipient_list)
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
        return False


def send_email_with_archive(subject, message, from_email, recipient_list, html_message=None, save_to_sent=True):
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
            html_message=html_message
        )
        
        # If email was sent successfully and archiving is enabled, save to Sent folder
        if result and save_to_sent:
            save_email_to_sent_folder(subject, message, from_email, recipient_list, html_message)
        
        return result
        
    except Exception as e:
        print(f"Email sending failed: {e}")
        return False

def format_aufgaben_email(aufgabe_name, aufgabe_deadline, base64_image, org_name, user_name, action_url, aufgabe_beschreibung='', unsubscribe_url=None):
    context = {
        'aufgabe_name': aufgabe_name,
        'aufgabe_beschreibung': aufgabe_beschreibung,
        'aufgabe_deadline': aufgabe_deadline.strftime('%d.%m.%Y') if aufgabe_deadline else '',
        'base64_image': base64_image,
        'org_name': org_name,
        'user_name': user_name,
        'action_url': action_url,
        'unsubscribe_url': unsubscribe_url
    }
    return render_to_string('mail/task_reminder.html', context)

def format_new_aufgaben_email(aufgaben, base64_image, org_name, user_name, action_url, unsubscribe_url=None):
    aufgaben_name = ', '.join([aufgabe.aufgabe.name for aufgabe in aufgaben])
    context = {
        'aufgaben_name': aufgaben_name,
        'base64_image': base64_image,
        'org_name': org_name,
        'user_name': user_name,
        'action_url': action_url,
        'unsubscribe_url': unsubscribe_url
    }
    return render_to_string('mail/new_tasks.html', context)

def format_aufgabe_erledigt_email(aufgabe_name, aufgabe_deadline, org_name, user_name, action_url, requires_confirmation=False, has_file_upload=False, aufgabe_beschreibung='', unsubscribe_url=None):
    # Convert boolean values to Yes/No text in German
    requires_confirmation_text = "Ja" if requires_confirmation else "Nein"
    has_file_upload_text = "Ja" if has_file_upload else "Nein"
    
    context = {
        'aufgabe_name': aufgabe_name,
        'aufgabe_beschreibung': aufgabe_beschreibung,
        'aufgabe_deadline': aufgabe_deadline.strftime('%d.%m.%Y') if aufgabe_deadline else '',
        'org_name': org_name,
        'user_name': user_name,
        'requires_confirmation': requires_confirmation_text,
        'has_file_upload': has_file_upload_text,
        'unsubscribe_url': unsubscribe_url,
        'action_button': has_file_upload,
        'action_url': action_url
    }
    return render_to_string('mail/task_completed.html', context)

def format_register_email_fw(einmalpasswort, action_url, base64_image, org_name, user_name, username):
    context = {
        'einmalpasswort': einmalpasswort,
        'action_url': action_url,
        'base64_image': base64_image,
        'org_name': org_name,
        'user_name': user_name,
        'username': username
    }
    return render_to_string('mail/register_volunteer.html', context)

def format_mail_calendar_reminder_email(title, start, end, description, action_url, unsubscribe_url, user_name, org_name, base64_image):
    event_name = title
    event_start = start.astimezone(timezone.get_current_timezone()).strftime('%d.%m.%Y %H:%M') if start else ''
    event_end = end.astimezone(timezone.get_current_timezone()).strftime('%d.%m.%Y %H:%M') if end else ''
    event_description = description if description else ''

    context = {
        'event_name': event_name,
        'event_start': event_start,
        'event_end': event_end,
        'event_description': event_description,
        'action_url': action_url,
        'unsubscribe_url': unsubscribe_url,
        'base64_image': base64_image,
        'org_name': org_name,
        'user_name': user_name
    }
    return render_to_string('mail/calendar_reminder.html', context)

def format_new_post_email(post_title, post_text, author_name, post_date, has_survey, action_url, unsubscribe_url, user_name, org_name, base64_image):
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
        'base64_image': base64_image
    }
    return render_to_string('mail/new_post.html', context)

def format_register_email_org(einmalpasswort, action_url, org_name, user_name, username):
    context = {
        'einmalpasswort': einmalpasswort,
        'action_url': action_url,
        'org_name': org_name,
        'user_name': user_name,
        'username': username
    }
    return render_to_string('mail/register_organization.html', context)

def get_logo_base64(org):
    with open(org.logo.path, "rb") as org_logo:
        base64_image = base64.b64encode(org_logo.read()).decode('utf-8')
    return base64_image

def send_aufgaben_email(aufgabe, org):
    # Get the organization logo URL
    action_url = 'https://volunteer.solutions/aufgaben/' + str(aufgabe.aufgabe.id) + "/"
    unsubscribe_url = aufgabe.user.customuser.get_unsubscribe_url()
    base64_image = get_logo_base64(org)
    aufg_name = aufgabe.aufgabe.name
    aufg_deadline = aufgabe.faellig
    aufg_beschreibung = aufgabe.aufgabe.beschreibung if aufgabe.aufgabe.beschreibung else ''
    user_name = f"{aufgabe.user.first_name} {aufgabe.user.last_name}"
    
    email_content = format_aufgaben_email(
        aufgabe_name=aufg_name,
        aufgabe_deadline=aufg_deadline,
        base64_image=base64_image,
        org_name=org.name,
        user_name=user_name,
        action_url=action_url,
        aufgabe_beschreibung=aufg_beschreibung,
        unsubscribe_url=unsubscribe_url
    )   
    
    subject = f'Erinnerung: {aufgabe.aufgabe.name}'

    push_content = f'Die Aufgabe "{aufgabe.aufgabe.name}" ist am {aufgabe.faellig.strftime("%d.%m.%Y")} fällig.'

    send_push_notification_to_user(aufgabe.user, subject, push_content, url=action_url)
    
    if aufgabe.user.customuser.mail_notifications and send_email_with_archive(subject, email_content, settings.SERVER_EMAIL, [aufgabe.user.email], html_message=email_content):
        aufgabe.last_reminder = timezone.now()
        aufgabe.currently_sending = False
        aufgabe.save()
        return True
    
    aufgabe.currently_sending = False
    aufgabe.save()
    
    push_content = f'Die Aufgabe "{aufgabe.aufgabe.name}" ist am {aufgabe.faellig.strftime("%d.%m.%Y")} fällig.'
    send_push_notification_to_user(aufgabe.user, subject, push_content, url=action_url)
    
    return False

def send_new_aufgaben_email(aufgaben, org):
    action_url = 'https://volunteer.solutions/aufgaben/'

    base64_image = get_logo_base64(org)

    email_content = format_new_aufgaben_email(
        aufgaben=aufgaben,
        base64_image=base64_image,
        org_name=org.name,
        user_name=f"{aufgaben[0].user.first_name} {aufgaben[0].user.last_name}",
        action_url=action_url,
        unsubscribe_url=aufgaben[0].user.customuser.get_unsubscribe_url()
    )

    subject = f'Neue Aufgaben: {aufgaben[0].aufgabe.name}... und mehr'
        
    if aufgaben[0].user.customuser.mail_notifications and send_email_with_archive(subject, email_content, settings.SERVER_EMAIL, [aufgaben[0].user.email], html_message=email_content):
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
    from django.urls import reverse
    
    post = Post2.objects.get(id=post_id)
    org = post.org
    
    # Generate action URL for the post
    action_url = f'{settings.DOMAIN_HOST}{reverse("post_detail", args=[post.pk])}'
    
    # Get organization logo
    base64_image = get_logo_base64(org)
    
    # Get author information
    author_name = f"{post.user.first_name} {post.user.last_name}" if post.user.first_name and post.user.last_name else post.user.username
    
    # Email subject
    subject = f'Neuer Post: {post.title}'
    
    # Track successful sends
    successful_sends = 0
    
    for person_cluster in post.person_cluster.all():
        for user in person_cluster.get_users():
            # Skip if user doesn't want email notifications
            if hasattr(user, 'customuser') and not user.customuser.mail_notifications:
                continue
                
            # Get user's unsubscribe URL
            unsubscribe_url = user.customuser.get_unsubscribe_url() if hasattr(user, 'customuser') else None
            
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
                base64_image=base64_image
            )
            
            # Send email using Django's send_mail
            if user.customuser.mail_notifications and send_email_with_archive(subject, '', settings.SERVER_EMAIL, [user.email], html_message=email_content):
                successful_sends += 1
                
            # Send push notification as well
            push_content = f'Neuer Post von {author_name}: {post.title}'
            if post.has_survey:
                push_content += ' (enthält Umfrage)'
                
            send_push_notification_to_user(user, subject, push_content, url=action_url)
    
    return successful_sends
    