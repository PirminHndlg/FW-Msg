import logging

from celery import shared_task
from django.conf import settings
from django.urls import reverse

from Global.send_email import (
    format_own_signin_accepted_email,
    format_own_signin_denied_email,
    format_own_signin_new_email,
    get_logo_url,
    get_org_color,
    send_email_with_archive,
)
from ORG.models import Organisation

logger = logging.getLogger(__name__)


@shared_task
def send_own_signin_org_notification_task(own_signin_user_id):
    from Home.models import OwnSigninUser

    try:
        own_signin_user = OwnSigninUser.objects.select_related(
            'org', 'person_cluster', 'land'
        ).get(id=own_signin_user_id)
    except OwnSigninUser.DoesNotExist:
        logger.error(f'OwnSigninUser with id {own_signin_user_id} does not exist')
        return False

    org = own_signin_user.org
    if not org.email:
        logger.warning(f'No email address for organization {org.id}')
        return False

    applicant_name = f'{own_signin_user.first_name} {own_signin_user.last_name}'.strip()
    action_url = f'{settings.DOMAIN_HOST}{reverse("review_own_signin_user", args=[own_signin_user.id])}'
    image_url = get_logo_url(org)
    org_color = get_org_color(org)

    email_content = format_own_signin_new_email(
        applicant_name=applicant_name,
        applicant_email=own_signin_user.email,
        person_cluster_name=own_signin_user.person_cluster.name,
        land_name=own_signin_user.land.name if own_signin_user.land else '',
        action_url=action_url,
        user_name=org.name,
        org_name=org.name,
        image_url=image_url,
        org_color=org_color,
    )
    subject = f'Neue Registrierungsanfrage: {applicant_name}'
    return send_email_with_archive(
        subject,
        email_content,
        settings.SERVER_EMAIL,
        [org.email],
        html_message=email_content,
        reply_to_list=[own_signin_user.email],
    )


@shared_task
def send_own_signin_accepted_email_task(applicant_email, applicant_name, org_id):
    try:
        org = Organisation.objects.get(id=org_id)
    except Organisation.DoesNotExist:
        logger.error(f'Organisation with id {org_id} does not exist')
        return False

    action_url = f'{settings.DOMAIN_HOST}{reverse("password_reset")}'
    image_url = get_logo_url(org)
    org_color = get_org_color(org)

    email_content = format_own_signin_accepted_email(
        applicant_name=applicant_name,
        action_url=action_url,
        org_name=org.name,
        image_url=image_url,
        org_color=org_color,
    )
    subject = f'Registrierung freigeschaltet: {org.name}'
    return send_email_with_archive(
        subject,
        email_content,
        settings.SERVER_EMAIL,
        [applicant_email],
        html_message=email_content,
    )


@shared_task
def send_own_signin_denied_email_task(applicant_email, applicant_name, org_id):
    try:
        org = Organisation.objects.get(id=org_id)
    except Organisation.DoesNotExist:
        logger.error(f'Organisation with id {org_id} does not exist')
        return False

    image_url = get_logo_url(org)
    org_color = get_org_color(org)

    email_content = format_own_signin_denied_email(
        applicant_name=applicant_name,
        org_name=org.name,
        image_url=image_url,
        org_color=org_color,
    )
    subject = f'Registrierung abgelehnt: {org.name}'
    return send_email_with_archive(
        subject,
        email_content,
        settings.SERVER_EMAIL,
        [applicant_email],
        html_message=email_content,
    )
