"""Login stages: admin_mfa's policy in allauth's login flow.

``AuthenticateStage`` replaces allauth's MFA stage (same key and URL, so
allauth's 2FA page keeps working) and decides per login: trusted network,
second factor, enrolment, or refusal. ``FinalizeStage`` runs last, after the
second factor and the trust-this-browser step, and only then writes the
session record the middleware checks. A login abandoned at the 2FA prompt
therefore leaves nothing behind that could be reused.
"""

from __future__ import annotations

import time

from allauth.account.stages import LoginStage
from allauth.core.internal.httpkit import headed_redirect_response
from allauth.mfa.stages import AuthenticateStage as AllauthAuthenticateStage
from allauth.mfa.webauthn.internal.flows import did_use_passwordless_login
from django.contrib import messages
from django.utils.translation import gettext as _

from . import audit, policy, session
from .policy import Decision

STATE_KEY = "admin_mfa"


class AuthenticateStage(AllauthAuthenticateStage):
    def handle(self):
        user = self.login.user
        if not policy.applies_to(user):
            return super().handle()
        if did_use_passwordless_login(self.request, user):
            # Signed in with a passkey: that already was the second factor.
            self.state[STATE_KEY] = {"mode": session.MODE_MFA, "rule": None}
            return super().handle()
        ip = policy.client_ip(self.request)
        decision, rule = policy.decide(user, ip)
        if decision is Decision.REFUSE:
            audit.event("login_refused", self.request, user, reason="no_second_factor")
            messages.error(
                self.request,
                _(
                    "Your account has no second factor yet. Log in once from the "
                    "office network and set one up (passkey or authenticator app)."
                ),
            )
            return headed_redirect_response("account_login"), False
        mode = {
            Decision.TRUSTED: session.MODE_TRUSTED,
            Decision.SECOND_FACTOR: session.MODE_MFA,
            Decision.ENROL: session.MODE_ENROL,
        }[decision]
        self.state[STATE_KEY] = {"mode": mode, "rule": str(rule) if rule else None}
        if decision is Decision.SECOND_FACTOR:
            return super().handle()
        return None, True


class FinalizeStage(LoginStage):
    key = "admin_mfa_finalize"

    def handle(self):
        user = self.login.user
        if not policy.applies_to(user):
            return None, True
        auth_stage = self.controller.get_stage(AuthenticateStage.key)
        data = auth_stage.state.get(STATE_KEY) if auth_stage else None
        if not data:
            # Our AuthenticateStage did not run: misconfigured stage list.
            audit.event("login_refused", self.request, user, reason="stage_missing")
            return headed_redirect_response("account_login"), False
        setup_since = time.time() if data["mode"] == session.MODE_ENROL else None
        session.mark(self.request, user, data["mode"], data.get("rule"), setup_since=setup_since)
        audit.event("login", self.request, user, mode=data["mode"], rule=data.get("rule"))
        return None, True
