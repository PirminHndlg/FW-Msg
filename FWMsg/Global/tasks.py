from celery import shared_task
import base64
from django.urls import reverse
from FWMsg import settings
import logging
from Global.send_email import send_new_post_email

@shared_task
def send_new_post_email_task(post_id):
    from Global.models import Post2
    post = Post2.objects.get(id=post_id)
    send_new_post_email(post_id)