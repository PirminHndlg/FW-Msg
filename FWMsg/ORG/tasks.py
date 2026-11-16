from django.conf import settings
from celery import shared_task
import base64
from django.urls import reverse
import logging
from FW.models import Freiwilliger
from TEAM.models import Team
from Global.notifications import (
    EMAIL,
    PUSH,
    NotificationType,
    filter_users_wanting,
    get_type_unsubscribe_url,
    notify_user,
)
from Global.push_notification import send_push_notification_to_user
from Global.send_email import format_register_email_org, format_aufgabe_erledigt_email, format_mail_calendar_reminder_email, format_ampel_email, get_org_color, send_email_with_archive, get_logo_url
from django.core.mail import send_mail
from django.contrib.auth.models import User


def _team_users_for_land(org, land):
    """Users of team members responsible for ``land``."""
    return User.objects.filter(
        team__org=org, team__land=land, customuser__isnull=False,
    ).distinct()


def _push_to_team(team_users, notification_type, subject, push_content, action_url):
    for team_user in filter_users_wanting(team_users, notification_type, PUSH):
        try:
            send_push_notification_to_user(team_user, subject, push_content, url=action_url)
        except Exception as e:
            logging.error(f"Error sending team push to user {team_user.id}: {e}")


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
    image_url = get_logo_url(org)
    org_color = get_org_color(org)
    email_content = format_register_email_org(einmalpasswort=einmalpasswort, action_url=action_url, org_name=org_name, user_name=freiwilliger_name, username=username, image_url=image_url, org_color=org_color)
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
        
        # only send email if aufgabe is erledigt or pending
        if not (aufgabe.erledigt or aufgabe.pending):
            return False
        
        mail_to = aufgabe.benachrichtigung_cc.split(',') if aufgabe.benachrichtigung_cc else []
        action_url = f"{settings.DOMAIN_HOST}{reverse('download_aufgabe', args=[aufgabe.id])}"
        has_file_upload = bool(aufgabe.file)
        org_color = get_org_color(aufgabe.user.org)
        
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
        team_users = User.objects.none()
        if aufgabe.aufgabe.visible_by_team and aufgabe.user.freiwilliger and aufgabe.user.freiwilliger.einsatzland2:
            team_users = _team_users_for_land(aufgabe.user.org, aufgabe.user.freiwilliger.einsatzland2)
            recipient_list.extend(
                filter_users_wanting(team_users, NotificationType.TEAM_TASK_DONE, EMAIL).values_list('email', flat=True)
            )

        recipient_list = [r for r in set(recipient_list) if r]

        push_content = f'{aufgabe.user.first_name} {aufgabe.user.last_name}: {aufgabe.aufgabe.name}'
        _push_to_team(team_users, NotificationType.TEAM_TASK_DONE, subject, push_content, action_url)

        if not recipient_list:
            return False
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

    if send_email_with_archive(subject, feedback.text, settings.SERVER_EMAIL, [secrets['feedback_email']], html_message=feedback.text, reply_to_list=[reply_to]):
        return True
    return False

@shared_task
def send_mail_calendar_reminder_task(kalender_event_id, user_id):
    from Global.models import KalenderEvent
    from Global.models import User
    from django.db import models
    try:
        kalender_event = KalenderEvent.objects.get(id=kalender_event_id)
        user = User.objects.get(id=user_id)
        
        if not kalender_event.user.filter(id=user.id).exists():
            return True  # user is not a participant

        if kalender_event.mail_reminder_sent_to.filter(id=user.id).exists():
            return True  # already reminded
        
        subject = f'Neuer Kalendereintrag: {kalender_event.title}'
        action_url = f"{settings.DOMAIN_HOST}{reverse('kalender_event', args=[kalender_event.id])}"
        unsubscribe_url = get_type_unsubscribe_url(user, NotificationType.CALENDAR_NEW)
        org_name = kalender_event.org.name
        user_name = f"{user.first_name} {user.last_name}"
        image_url = get_logo_url(kalender_event.org)
        org_color = get_org_color(kalender_event.org)
        email_content = format_mail_calendar_reminder_email(title=kalender_event.title, start=kalender_event.start, end=kalender_event.end, location=kalender_event.location, description=kalender_event.description, action_url=action_url, unsubscribe_url=unsubscribe_url, user_name=user_name, org_name=org_name, image_url=image_url, org_color=org_color)
        push_content = f'{kalender_event.start.strftime("%d.%m.%Y")} bis {kalender_event.end.strftime("%d.%m.%Y")}: {kalender_event.title}'
        sent = notify_user(
            user, NotificationType.CALENDAR_NEW, subject,
            email_html=email_content, push_body=push_content, url=action_url,
            reply_to=[user.org.email] if user.org.email else None,
        )
        # Mark as handled even for users who opted out, so a later save of the
        # event doesn't queue another reminder for them.
        kalender_event.mail_reminder_sent_to.add(user)
        return bool(sent[EMAIL] or sent[PUSH])
    except models.DoesNotExist:
        # kalender event has been deleted before email was sent
        return True
    except Exception as e:
        logging.error(f"Error sending mail calendar reminder task: {e}")
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
        
        user_email = user.email
        
        # Create action URL - link to the ampel overview page or user profile
        action_url = f"{settings.DOMAIN_HOST}{reverse('list_ampel')}"
        
        # Get organization logo as base64
        image_url = get_logo_url(org)
        org_color = get_org_color(org)
        
        # Format the email content
        email_content = format_ampel_email(
            user_name=org.name,
            ampel_user_name=user_name,
            ampel_user_email=user_email,
            status=ampel.status,
            comment=ampel.comment,
            ampel_date=ampel.date,
            action_url=action_url,
            unsubscribe_url=None,  # Organizations don't have unsubscribe URLs
            org_name=org.name,
            image_url=image_url,
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
        
        try:
            land = Freiwilliger.objects.get(user=ampel.user).einsatzland2
            team_users = _team_users_for_land(org, land) if land else User.objects.none()
            team_emails = list(
                filter_users_wanting(team_users, NotificationType.TEAM_AMPEL_NEW, EMAIL)
                .values_list('email', flat=True)
                .distinct()
            )
        except Exception as e:
            logging.error(f"Error getting team members: {e}")
            team_users = User.objects.none()
            team_emails = []

        push_content = f'{user_name}: Status {status_text}'
        if ampel.comment:
            push_content += f' – {ampel.comment}'
        _push_to_team(team_users, NotificationType.TEAM_AMPEL_NEW, subject, push_content, action_url)

        recipient_list = ([org.email] if org.email else []) + team_emails
        if not org.email:
            logging.warning(f"No email address found for organization {org.id}")
        if not recipient_list:
            return False

        return send_email_with_archive(
            subject=subject,
            message=email_content,
            from_email=settings.SERVER_EMAIL,
            recipient_list=recipient_list,
            html_message=email_content,
            reply_to_list=[user_email]
        )
            
    except Ampel2.DoesNotExist:
        logging.error(f"Ampel with id {ampel_id} does not exist")
        return False
    except Exception as e:
        logging.error(f"Error sending ampel email: {e}")
        return False