from celery import shared_task
import base64
from django.urls import reverse
from FWMsg import settings
import logging
from django.core.mail import send_mail

@shared_task
def send_new_post_email_task(post_id):
    from Global.send_email import send_new_post_email
    return send_new_post_email(post_id)