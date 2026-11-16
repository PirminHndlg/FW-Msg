"""Who needs which factor, from where.

Applies to active staff users and superusers, or to whom the site's
``ADMIN_MFA_APPLIES_TO`` names. Other users keep the site's own login; if
they log in through allauth at all, they get allauth's default.
"""

from __future__ import annotations

import enum

from allauth.account.adapter import get_adapter as get_account_adapter
from allauth.mfa.models import Authenticator
from django.http import HttpRequest
from django.utils.module_loading import import_string

from . import conf

SECOND_FACTOR_TYPES = (Authenticator.Type.TOTP, Authenticator.Type.WEBAUTHN)


class Decision(enum.Enum):
    TRUSTED = "trusted"  # trusted network: password is enough
    SECOND_FACTOR = "mfa"  # allauth's MFA step decides (passkey, trusted browser)
    ENROL = "enrol"  # no second factor yet: login leads to the setup page only
    REFUSE = "refuse"  # no second factor, and not allowed to set one up from here


def staff_or_superuser(user) -> bool:
    return bool(user.is_staff or user.is_superuser)


def applies_to(user) -> bool:
    if not (user and getattr(user, "is_active", False)):
        return False
    return bool(import_string(conf.applies_to_path())(user))


def has_second_factor(user) -> bool:
    return Authenticator.objects.filter(user=user, type__in=SECOND_FACTOR_TYPES).exists()


def client_ip(request: HttpRequest) -> str:
    # allauth's resolution: ALLAUTH_TRUSTED_PROXY_COUNT entries from the right
    # of X-Forwarded-For, else REMOTE_ADDR. The same IP its rate limits use.
    return get_account_adapter(request).get_client_ip(request)


def matching_network(user, ip: str | None) -> conf.TrustedNetwork | None:
    """The first trusted-network rule that covers this user at this IP."""
    username = user.get_username()
    for rule in conf.trusted_networks():
        if rule.matches(ip, username):
            return rule
    return None


def trusted_rule(user, ip: str | None) -> conf.TrustedNetwork | None:
    """The rule that lets this user skip the second factor, if any."""
    if user.is_superuser and conf.superuser_always():
        return None
    return matching_network(user, ip)


def may_enrol(user, ip: str | None) -> bool:
    if conf.first_enrolment() == "anywhere":
        return True
    return matching_network(user, ip) is not None


def decide(user, ip: str | None) -> tuple[Decision, conf.TrustedNetwork | None]:
    rule = trusted_rule(user, ip)
    if rule is not None:
        return Decision.TRUSTED, rule
    if has_second_factor(user):
        return Decision.SECOND_FACTOR, None
    if may_enrol(user, ip):
        return Decision.ENROL, None
    return Decision.REFUSE, None
