from django.conf import settings
from celery import shared_task
import base64
from django.urls import reverse
import logging
from FW.models import Freiwilliger
from TEAM.models import Team
from Global.push_notification import send_push_notification_to_user
from Global.send_email import format_register_email_org, format_aufgabe_erledigt_email, format_mail_calendar_reminder_email, format_ampel_email, get_org_color, send_email_with_archive, get_logo_base64
from django.core.mail import send_mail


@shared_task
def send_register_email_task(customuser_id):
    from Global.models import CustomUser

    try:
        customuser = CustomUser.objects.get(id=customuser_id)
    except CustomUser.DoesNotExist:
        logging.error(f"CustomUser with id {customuser_id} does not exist")
        return False
    
    user = customuser.user
    org = customuser.org

    org_name = org.name
    einmalpasswort = customuser.einmalpasswort
    freiwilliger_name = f"{user.first_name} {user.last_name}"
    username = user.username
    action_url = f'{settings.DOMAIN_HOST}{reverse("first_login_with_params", args=[username, einmalpasswort])}'
    base64_image = get_logo_base64(org)
    org_color = get_org_color(org)
    email_content = format_register_email_org(einmalpasswort=einmalpasswort, action_url=action_url, org_name=org_name, user_name=freiwilliger_name, username=username, base64_image=base64_image, org_color=org_color)
    subject = f'Account erstellt: {freiwilliger_name}'
    if send_email_with_archive(subject, email_content, settings.SERVER_EMAIL, [user.email], html_message=email_content):
        return True
    logging.error(f"Error sending register email: {user.email} {subject}")
    return False

@shared_task
def send_aufgabe_erledigt_email_task(aufgabe_id):
    from Global.models import UserAufgaben
    
    try:
        aufgabe = UserAufgaben.objects.get(id=aufgabe_id)
        if not aufgabe.aufgabe.with_email_notification:
            return False
        mail_to = aufgabe.benachrichtigung_cc.split(',') if aufgabe.benachrichtigung_cc else []
        
        # Create action URL
        action_url = f"{settings.DOMAIN_HOST}{reverse('download_aufgabe', args=[aufgabe.id])}"
        
        # Check if there's a file uploaded
        has_file_upload = bool(aufgabe.file)
        
        org_color = get_org_color(aufgabe.user.org)
        
        # Format the email with our template
        email_content = format_aufgabe_erledigt_email(
            aufgabe_name=aufgabe.aufgabe.name,
            aufgabe_deadline=aufgabe.faellig,
            org_color=org_color,
            org_name=aufgabe.user.org.name,
            user_name=f"{aufgabe.user.first_name} {aufgabe.user.last_name}",
            action_url=action_url,
            requires_confirmation=aufgabe.aufgabe.requires_submission,
            has_file_upload=has_file_upload
        )
        
        subject = f'Aufgabe erledigt: {aufgabe.aufgabe.name} von {aufgabe.user.first_name} {aufgabe.user.last_name}'
        org_email = aufgabe.user.org.email
        recipient_list = [org_email]
        if mail_to:
            recipient_list.extend(mail_to)
        recipient_list = list(set(recipient_list))
        
        return send_email_with_archive(subject, email_content, settings.SERVER_EMAIL, recipient_list, html_message=email_content)
    except Exception as e:
        logging.error(f"Error sending task completion email: {e}")
        return False

@shared_task
def send_feedback_email_task(feedback_id):
    from Global.models import Feedback
    import json

    with open('FWMsg/.secrets.json', 'r') as f:
        secrets = json.load(f)

    feedback = Feedback.objects.get(id=feedback_id)
    subject = f'Feedback von {feedback.user.username}' if not feedback.anonymous else 'Anonymes Feedback'
    reply_to = feedback.user.email if not feedback.anonymous else None

    if send_email_with_archive(subject, feedback.text, settings.SERVER_EMAIL, [secrets['feedback_email']], html_message=feedback.text):
        return True
    return False

@shared_task
def send_mail_calendar_reminder_task(kalender_event_id, user_id):
    from Global.models import KalenderEvent
    from Global.models import User
    kalender_event = KalenderEvent.objects.get(id=kalender_event_id)
    user = User.objects.get(id=user_id)
    subject = f'Neuer Kalendereintrag: {kalender_event.title}'
    action_url = f"{settings.DOMAIN_HOST}{reverse('kalender_event', args=[kalender_event.id])}"
    unsubscribe_url = user.customuser.get_unsubscribe_url()
    org_name = kalender_event.org.name
    user_name = f"{user.first_name} {user.last_name}"
    base64_image = get_logo_base64(kalender_event.org)
    org_color = get_org_color(kalender_event.org)
    
    email_content = format_mail_calendar_reminder_email(title=kalender_event.title, start=kalender_event.start, end=kalender_event.end, location=kalender_event.location, description=kalender_event.description, action_url=action_url, unsubscribe_url=unsubscribe_url, user_name=user_name, org_name=org_name, base64_image=base64_image, org_color=org_color)
    
    push_content = f'{kalender_event.start.strftime("%d.%m.%Y")} bis {kalender_event.end.strftime("%d.%m.%Y")}: {kalender_event.title}'
    send_push_notification_to_user(user, subject, push_content, url=action_url)
    
    if user.customuser.mail_notifications and send_email_with_archive(subject, email_content, settings.SERVER_EMAIL, [user.email], html_message=email_content):
        return True
    return False

@shared_task
def send_ampel_email_task(ampel_id):
    """Send email notification to organization when a user submits an ampel status"""
    from Global.models import Ampel2
    
    try:
        ampel = Ampel2.objects.get(id=ampel_id)
        user = ampel.user
        org = ampel.org
        
        # Get user's full name
        user_name = f"{user.first_name} {user.last_name}".strip()
        if not user_name:
            user_name = user.username
        
        # Create action URL - link to the ampel overview page or user profile
        action_url = f"{settings.DOMAIN_HOST}{reverse('list_ampel')}"
        
        # Get organization logo as base64
        base64_image = get_logo_base64(org)
        org_color = get_org_color(org)
        
        # Format the email content
        email_content = format_ampel_email(
            user_name=org.name,
            ampel_user_name=user_name,
            ampel_user_email=user.email,
            status=ampel.status,
            comment=ampel.comment,
            ampel_date=ampel.date,
            action_url=action_url,
            unsubscribe_url=None,  # Organizations don't have unsubscribe URLs
            org_name=org.name,
            base64_image=base64_image,
            org_color=org_color
        )
        
        # Create subject based on status
        status_text = {
            'G': 'Grün',
            'Y': 'Gelb',
            'R': 'Rot'
        }.get(ampel.status, 'Unbekannt')
        
        status_emoji = {
            'G': '🟢',
            'Y': '🟡',
            'R': '🔴'
        }.get(ampel.status, '❓')
        
        subject = f'{status_emoji} Neue Ampelmeldung: {user_name} - Status {status_text}'
        
        # Send email to organization
        if org.email:
            try:
                land = Freiwilliger.objects.get(user=ampel.user).einsatzland2
                team_emails = list(
                    Team.objects.filter(org=org, land=land, user__email__isnull=False, user__customuser__isnull=False, user__customuser__mail_notifications=True)
                    .exclude(user__email='')
                    .values_list('user__email', flat=True)
                    .distinct()
                )
            except Exception as e:
                logging.error(f"Error getting team members: {e}")
                team_emails = []

            return send_email_with_archive(
                subject=subject,
                message=email_content,
                from_email=settings.SERVER_EMAIL,
                recipient_list=[org.email] + team_emails,
                html_message=email_content
            )
        else:
            logging.warning(f"No email address found for organization {org.id}")
            return False
            
    except Ampel2.DoesNotExist:
        logging.error(f"Ampel with id {ampel_id} does not exist")
        return False
    except Exception as e:
        logging.error(f"Error sending ampel email: {e}")
        return False