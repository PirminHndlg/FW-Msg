import base64
from django.conf import settings
from django.urls import reverse
from celery import shared_task
from Global.send_email import format_register_email_fw, get_logo_url, get_org_color, send_email_with_archive
import logging

@shared_task
def send_register_email_task(custom_user_id):
    from Global.models import CustomUser
    try:
        custom_user = CustomUser.objects.get(id=custom_user_id)
        org = custom_user.org

        image_url = get_logo_url(org)
        org_color = get_org_color(org)
        org_name = org.name
        einmalpasswort = custom_user.einmalpasswort
        user_name = f"{custom_user.user.first_name} {custom_user.user.last_name}"
        username = custom_user.user.username
        action_url = f'{settings.DOMAIN_HOST}{reverse("first_login_with_params", args=[username, einmalpasswort])}'
        
        email_content = format_register_email_fw(einmalpasswort, action_url, image_url, org_color, org_name, user_name, username)
        subject = f'Account erstellt: {user_name}'
        return send_email_with_archive(subject, email_content, settings.SERVER_EMAIL, [custom_user.user.email], html_message=email_content)
    
    except Exception as e:
        logging.error(f"Error sending register email task: {e}")
        return False