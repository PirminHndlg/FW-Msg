from celery import shared_task
from django.urls import reverse
from django.conf import settings
import logging
from Global.send_email import (
    format_image_uploaded_email,
    get_org_color,
    send_email_with_archive,
    get_logo_base64,
    send_new_post_email
)

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
        base64_image = get_logo_base64(org)
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
            base64_image=base64_image,
            org_color=org_color
        )

        send_email_with_archive(
            subject,
            email_content,
            settings.SERVER_EMAIL,
            [org_email],
            html_message=email_content,
        )
        return True
    except Exception as e:
        logging.error(f"Error sending image uploaded email task: {e}")
        return False


@shared_task
def send_birthday_reminder_email_task(user_id):
    from Global.models import CustomUser

    custom_user = CustomUser.objects.get(id=user_id)
    org = custom_user.org
    receiver = [org.email]
    from Global.send_email import format_birthday_reminder_email
    
    subject = f'Morgen ist der Geburtstag von {custom_user.user.first_name} {custom_user.user.last_name}'

    email_content = format_birthday_reminder_email(
        custom_user.user.first_name + ' ' + custom_user.user.last_name,
        custom_user.user.email,
        custom_user.geburtsdatum,
        custom_user.get_unsubscribe_url(),
        org.name,
        get_logo_base64(org),
        get_org_color(org),
    )
    send_email_with_archive(
        subject,
        email_content,
        settings.SERVER_EMAIL,
        receiver,
        html_message=email_content,
    )
