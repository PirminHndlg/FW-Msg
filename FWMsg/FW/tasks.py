import base64
from datetime import datetime, timedelta
from django.db.models import Q
from django.urls import reverse
from FWMsg import settings
from celery import shared_task

from django.contrib.auth.models import User
from Global.send_email import send_mail_smtp, format_register_email_fw



@shared_task
def send_register_email_task(user_id):
    user = User.objects.get(id=user_id)
    org = user.customuser.org

    with open(org.logo.path, "rb") as org_logo:
        base64_image = base64.b64encode(org_logo.read()).decode('utf-8')
    org_name = org.name
    einmalpasswort = user.customuser.einmalpasswort
    user_name = f"{user.first_name} {user.last_name}"
    username = user.username
    action_url = f'{settings.DOMAIN_HOST}{reverse("first_login_with_params", args=[username, einmalpasswort])}'
    
    email_content = format_register_email_fw(einmalpasswort, action_url, base64_image, org_name, user_name, username)
    subject = f'Account erstellt: {user_name}'
    if send_mail_smtp(user.email, subject, email_content, reply_to=org.email):
        return True
    return False
