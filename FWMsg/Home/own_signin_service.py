from django.contrib.auth import get_user_model
from django.utils.translation import gettext as _

from BW.models import Bewerber
from Ehemalige.models import Ehemalige
from FW.models import Freiwilliger
from Global.models import get_or_create_new_user
from TEAM.models import Team

from .models import OwnSigninUser


class OwnSigninApprovalError(Exception):
    pass


def approve_own_signin_user(own_signin_user):
    """Create a real user account from a pending registration and delete the request."""
    User = get_user_model()
    email = own_signin_user.email
    org = own_signin_user.org
    person_cluster = own_signin_user.person_cluster

    if User.objects.filter(email__iexact=email).exists():
        raise OwnSigninApprovalError(
            _('Ein Benutzer mit dieser E-Mail-Adresse existiert bereits.')
        )

    user = get_or_create_new_user(
        email=email,
        firstname=own_signin_user.first_name,
        lastname=own_signin_user.last_name,
        org=org,
        person_cluster=person_cluster,
        create_einmalpasswort=False,
        create_customuser=True,
    )

    view = person_cluster.view
    land = own_signin_user.land

    if view == 'F':
        freiwilliger, created = Freiwilliger.objects.get_or_create(user=user, org=org)
        if land:
            freiwilliger.einsatzland2 = land
            freiwilliger.save()
    elif view == 'T':
        team, created = Team.objects.get_or_create(user=user, org=org)
        if land:
            team.land.add(land)
    elif view == 'B':
        Bewerber.objects.get_or_create(user=user, org=org)
    elif view == 'E':
        ehemalige, created = Ehemalige.objects.get_or_create(user=user, org=org)
        if land:
            ehemalige.land.add(land)

    applicant_email = own_signin_user.email
    applicant_name = f'{own_signin_user.first_name} {own_signin_user.last_name}'.strip()
    org_id = org.id
    own_signin_user.delete()

    from Home.tasks import send_own_signin_accepted_email_task
    send_own_signin_accepted_email_task.delay(applicant_email, applicant_name, org_id)

    return user


def deny_own_signin_user(own_signin_user):
    """Reject a pending registration and notify the applicant."""
    applicant_email = own_signin_user.email
    applicant_name = f'{own_signin_user.first_name} {own_signin_user.last_name}'.strip()
    org_id = own_signin_user.org_id
    own_signin_user.delete()

    from Home.tasks import send_own_signin_denied_email_task
    send_own_signin_denied_email_task.delay(applicant_email, applicant_name, org_id)
