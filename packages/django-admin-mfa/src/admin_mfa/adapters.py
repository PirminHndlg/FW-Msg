from __future__ import annotations

from allauth.account.adapter import DefaultAccountAdapter
from allauth.mfa.adapter import DefaultMFAAdapter
from allauth.mfa.models import Authenticator
from django.core.exceptions import ImproperlyConfigured

from . import policy, session

ALLAUTH_MFA_STAGE = "allauth.mfa.stages.AuthenticateStage"


class AccountAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request) -> bool:
        return False

    def get_login_stages(self) -> list[str]:
        stages = super().get_login_stages()
        if ALLAUTH_MFA_STAGE not in stages:
            raise ImproperlyConfigured("admin_mfa needs allauth.mfa in INSTALLED_APPS")
        stages = [
            "admin_mfa.stages.AuthenticateStage" if s == ALLAUTH_MFA_STAGE else s for s in stages
        ]
        stages.append("admin_mfa.stages.FinalizeStage")
        return stages

    def is_reauthentication_required(self, *, app: str, **kwargs) -> bool:
        """No second password prompt while a user sets up their first factor.

        allauth asks for the password before any change to the 2FA setup and
        does not count the login itself, so a first enrolment asked for the
        password twice within seconds (and password managers, seeing no
        username on that page, often filled in the wrong one). A recent
        first-enrolment login (``ADMIN_MFA_SETUP_GRACE``) is enough.
        """
        request = self.request
        user = getattr(request, "user", None) if request is not None else None
        if (
            app == "allauth.mfa"
            and user is not None
            and user.is_authenticated
            and policy.applies_to(user)
            and session.in_setup_grace(request, user)
        ):
            return False
        return super().is_reauthentication_required(app=app, **kwargs)


class MFAAdapter(DefaultMFAAdapter):
    def can_delete_authenticator(self, authenticator: Authenticator) -> bool:
        """Staff keep at least one second factor (TOTP deactivation form).

        Removing the last passkey is guarded in AdminMFAMiddleware, since
        allauth's WebAuthn removal view does not ask the adapter.
        """
        if not policy.applies_to(authenticator.user):
            return super().can_delete_authenticator(authenticator)
        if authenticator.type not in policy.SECOND_FACTOR_TYPES:
            return True
        others = Authenticator.objects.filter(
            user=authenticator.user, type__in=policy.SECOND_FACTOR_TYPES
        ).exclude(pk=authenticator.pk)
        return others.exists()
