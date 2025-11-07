from celery import shared_task
from django.urls import reverse
from django.conf import settings
import logging
from Global.send_email import (
    format_image_uploaded_email,
    format_change_request_new_email,
    format_change_request_decision_email,
    get_org_color,
    send_email_with_archive,
    get_logo_url,
    send_new_post_email
)
from django.db import models

@shared_task
def send_new_post_email_task(post_id):
    return send_new_post_email(post_id)

@shared_task
def send_image_uploaded_email_task(bild_id):
    """Send an email to the organization when a new image is uploaded."""
    from Global.models import Bilder2, BilderGallery2

    try:
        bild = Bilder2.objects.get(id=bild_id)
        org = bild.org

        image_id = getattr(bild, 'id', None)
        if not image_id:
            return False
        action_url = f"{settings.DOMAIN_HOST}{reverse('image_detail', args=[image_id])}"
        subject = f"Neues Bild hochgeladen: {bild.titel}"
        org_email = org.email
        uploader_name = f"{bild.user.first_name} {bild.user.last_name}".strip() or bild.user.username
        image_url = get_logo_url(org)
        org_color = get_org_color(org)
        unsubscribe_url = None
        user_name = org.name
        org_name = org.name
        image_count = BilderGallery2.objects.filter(bilder=bild).count()

        email_content = format_image_uploaded_email(
            bild_titel=bild.titel,
            bild_beschreibung=bild.beschreibung or '',
            uploader_name=uploader_name,
            image_count=image_count,
            action_url=action_url,
            unsubscribe_url=unsubscribe_url,
            user_name=user_name,
            org_name=org_name,
            image_url=image_url,
            org_color=org_color
        )

        send_email_with_archive(
            subject,
            email_content,
            settings.SERVER_EMAIL,
            [org_email],
            html_message=email_content,
            reply_to_list=[bild.user.email]
        )
        return True
    except models.DoesNotExist:
        # image has been deleted before email was sent
        return True
    except Exception as e:
        logging.error(f"Error sending image uploaded email task: {e}")
        return False


@shared_task
def send_birthday_reminder_email_task(user_id, is_tomorrow=True):
    from Global.models import CustomUser

    custom_user = CustomUser.objects.get(id=user_id)
    org = custom_user.org
    receiver = [org.email]
    from Global.send_email import format_birthday_reminder_email
    
    if is_tomorrow:
        subject = f'Morgen hat {custom_user.user.first_name} {custom_user.user.last_name} Geburtstag'
    else:
        subject = f'Heute hat {custom_user.user.first_name} {custom_user.user.last_name} Geburtstag'

    email_content = format_birthday_reminder_email(
        birthday_user_name=f"{custom_user.user.first_name} {custom_user.user.last_name}",
        user_email=custom_user.user.email,
        birthday=custom_user.geburtsdatum,
        org_name=org.name,
        image_url=get_logo_url(org),
        org_color=get_org_color(org),
        is_tomorrow=is_tomorrow
    )
    send_email_with_archive(
        subject,
        email_content,
        settings.SERVER_EMAIL,
        receiver,
        html_message=email_content,
    )


@shared_task
def send_change_request_new_email_task(change_request_id):
    """Send email notification to organization member about new change request."""
    from Global.models import ChangeRequest
    from django.contrib.auth.models import User
    from Global.push_notification import send_push_notification_to_user
    
    try:
        change_request = ChangeRequest.objects.get(id=change_request_id)
        org = change_request.org
        
        # Prepare email content
        obj_name = change_request.get_object_name()
        requester_name = f"{change_request.requested_by.first_name} {change_request.requested_by.last_name}"
        if not requester_name.strip():
            requester_name = change_request.requested_by.username
        
        change_type_display = change_request.get_change_type_display()
        
        # Get organization logo and color
        image_url = get_logo_url(change_request.org)
        org_color = get_org_color(change_request.org)
        
        # Generate action URL
        action_url = f'{settings.DOMAIN_HOST}{reverse("review_change_request", args=[change_request.id])}'
        
        subject = f'Neuer Änderungsvorschlag: {change_type_display} - {obj_name}'
        
        user_name = f"{org.name}"
        if not user_name.strip():
            user_name = org.name
        
        # Generate HTML email
        email_content = format_change_request_new_email(
            change_type=change_type_display,
            object_name=obj_name,
            requester_name=requester_name,
            reason=change_request.reason,
            action_url=action_url,
            user_name=user_name,
            org_name=change_request.org.name,
            image_url=image_url,
            org_color=org_color
        )
        
        # Send email if user has notifications enabled
        send_email_with_archive(
            subject=subject,
            message='',  # Plain text fallback
            from_email=settings.SERVER_EMAIL,
            recipient_list=[org.email],
            html_message=email_content,
            reply_to_list=[change_request.requested_by.email] if change_request.requested_by.email else None
        )
        
        return True
        
    except models.DoesNotExist:
        # change request has been deleted before email was sent
        return True
    except Exception as e:
        logging.error(f"Error in send_change_request_new_email_task: {e}")
        return False


@shared_task
def send_change_request_decision_email_task(change_request_id):
    """Send email notification to requester about change request decision."""
    from Global.models import ChangeRequest
    from Global.push_notification import send_push_notification_to_user
    
    try:
        change_request = ChangeRequest.objects.get(id=change_request_id)
        user = change_request.requested_by
        
        obj_name = change_request.get_object_name()
        reviewer_name = f"{change_request.reviewed_by.first_name} {change_request.reviewed_by.last_name}" if change_request.reviewed_by else "Administrator"
        if not reviewer_name.strip() or reviewer_name == " ":
            reviewer_name = change_request.reviewed_by.username if change_request.reviewed_by else "Administrator"
        
        user_name = f"{user.first_name} {user.last_name}"
        if not user_name.strip():
            user_name = user.username
        
        status = change_request.status
        status_display = change_request.get_status_display()
        change_type_display = change_request.get_change_type_display()
        
        # Get organization logo and color
        image_url = get_logo_url(change_request.org)
        org_color = get_org_color(change_request.org)
        
        # Generate action URL - redirect to their info page
        action_url = f'{settings.DOMAIN_HOST}{reverse("laender_info")}'
        
        # Get unsubscribe URL
        unsubscribe_url = user.customuser.get_unsubscribe_url() if hasattr(user, 'customuser') else None
        
        subject = f'Änderungsvorschlag {status_display}: {change_type_display} - {obj_name}'
        
        # Generate HTML email
        email_content = format_change_request_decision_email(
            status=status,
            status_display=status_display,
            change_type=change_type_display,
            object_name=obj_name,
            reviewer_name=reviewer_name,
            review_comment=change_request.review_comment,
            action_url=action_url,
            unsubscribe_url=unsubscribe_url,
            user_name=user_name,
            org_name=change_request.org.name,
            image_url=image_url,
            org_color=org_color
        )
        
        # Send email if user has notifications enabled
        if hasattr(user, 'customuser') and user.customuser.mail_notifications:
            send_email_with_archive(
                subject=subject,
                message='',  # Plain text fallback
                from_email=settings.SERVER_EMAIL,
                recipient_list=[user.email],
                html_message=email_content,
                reply_to_list=[change_request.org.email] if change_request.org.email else None
            )
        
        # Send push notification
        status_text = "genehmigt" if status == 'approved' else "abgelehnt"
        send_push_notification_to_user(
            user,
            subject,
            f'Änderungsvorschlag {status_text}',
            url=reverse('laender_info')  # Redirect to their info page
        )
        
        return True
        
    except models.DoesNotExist:
        # change request has been deleted before email was sent
        return True
    except Exception as e:
        logging.error(f"Error in send_change_request_decision_email_task: {e}")
        return False
