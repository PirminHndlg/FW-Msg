"""Session checks for staff, and allauth's surface cut down to what is used."""

from __future__ import annotations

from allauth.mfa.models import Authenticator
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.views import redirect_to_login
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import resolve_url
from django.urls import reverse
from django.utils.translation import gettext as _

from . import audit, conf, policy, session

# allauth views that stay reachable. Signup, password reset, e-mail and phone
# management, login by code and social accounts answer 404: these sites have
# no self-service accounts, and password reset by e-mail is not set up.
ALLOWED_ALLAUTH_URLS = frozenset(
    {
        "account_login",
        "account_logout",
        "account_inactive",
        "account_reauthenticate",
        "mfa_index",
        "mfa_authenticate",
        "mfa_reauthenticate",
        "mfa_trust",
        "mfa_activate_totp",
        "mfa_deactivate_totp",
        "mfa_view_recovery_codes",
        "mfa_generate_recovery_codes",
        "mfa_download_recovery_codes",
        "mfa_add_webauthn",
        "mfa_list_webauthn",
        "mfa_edit_webauthn",
        "mfa_remove_webauthn",
        "mfa_login_webauthn",
        "mfa_reauthenticate_webauthn",
    }
)

# What a staff user without a second factor may open after an enrolment login.
ENROL_URLS = frozenset(
    {
        "account_logout",
        "account_reauthenticate",
        "mfa_index",
        "mfa_reauthenticate",
        "mfa_activate_totp",
        "mfa_add_webauthn",
        "mfa_list_webauthn",
        "mfa_view_recovery_codes",
        "mfa_generate_recovery_codes",
        "mfa_download_recovery_codes",
    }
)


# The 2FA pages a signed-in user reaches outside the login flow. Only users
# the policy applies to: anyone else logs in through the site's own login,
# which has no second-factor step, so a factor set up here would protect
# nothing.
SETUP_URLS = frozenset(
    {
        "mfa_index",
        "mfa_activate_totp",
        "mfa_deactivate_totp",
        "mfa_view_recovery_codes",
        "mfa_generate_recovery_codes",
        "mfa_download_recovery_codes",
        "mfa_add_webauthn",
        "mfa_list_webauthn",
        "mfa_edit_webauthn",
        "mfa_remove_webauthn",
    }
)


def _is_allauth_view(view_func) -> bool:
    module = getattr(view_func, "__module__", "") or ""
    return module == "allauth" or module.startswith("allauth.")


class AdminMFAMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        match = request.resolver_match
        url_name = match.url_name if match else None
        if _is_allauth_view(view_func) and url_name not in ALLOWED_ALLAUTH_URLS:
            raise Http404

        user = getattr(request, "user", None)
        if not (user is not None and user.is_authenticated):
            return None
        if not policy.applies_to(user):
            if url_name in SETUP_URLS:
                raise Http404
            return None

        if url_name == "mfa_remove_webauthn" and request.method == "POST":
            response = self._guard_last_passkey(request, user, view_kwargs)
            if response is not None:
                return response

        if not conf.enforce():
            return None

        state = session.get(request, user)
        if state is None:
            return self._end(request, user, "no_login_record", _("Please log in again."))

        mode = state.get("mode")
        if mode == session.MODE_TRUSTED:
            ip = policy.client_ip(request)
            if policy.trusted_rule(user, ip) is None:
                return self._end(
                    request,
                    user,
                    "left_trusted_network",
                    _("You are no longer on a trusted network. Please log in again."),
                )
            return None

        if mode == session.MODE_ENROL:
            if policy.has_second_factor(user):
                # Keep setup_since: the recovery codes shown right after the
                # first factor must not ask for the password again.
                session.mark(request, user, session.MODE_MFA, setup_since=state.get("setup_since"))
                audit.event("enrolled", request, user)
                return None
            if url_name in ENROL_URLS:
                return None
            messages.warning(
                request,
                _("Set up a second factor (passkey or authenticator app) to continue."),
            )
            return HttpResponseRedirect(reverse("mfa_index"))

        if mode == session.MODE_MFA:
            return None

        return self._end(request, user, "unknown_login_record", _("Please log in again."))

    def _end(self, request, user, reason: str, message: str):
        audit.event("session_ended", request, user, reason=reason)
        path = request.get_full_path()
        logout(request)
        messages.info(request, message)
        return redirect_to_login(path, resolve_url(conf.login_url()))

    def _guard_last_passkey(self, request, user, view_kwargs):
        target = view_kwargs.get("pk")
        others = Authenticator.objects.filter(user=user, type__in=policy.SECOND_FACTOR_TYPES)
        if target is not None:
            others = others.exclude(pk=target)
        if others.exists():
            return None
        messages.error(
            request,
            _("This is your only second factor. Add another one before removing it."),
        )
        return HttpResponseRedirect(reverse("mfa_list_webauthn"))
