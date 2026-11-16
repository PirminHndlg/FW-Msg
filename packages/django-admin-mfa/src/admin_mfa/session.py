"""The login record admin_mfa keeps in the session.

Written by the last login stage, i.e. only by a login that went through
allauth's flow with admin_mfa's policy. A staff session without it (Django's
own LoginView, a session from before the rollout) is not accepted.
"""

from __future__ import annotations

import time

from . import conf

KEY = "admin_mfa"

MODE_TRUSTED = "trusted"
MODE_MFA = "mfa"
MODE_ENROL = "enrol"


def mark(
    request, user, mode: str, rule: str | None = None, *, setup_since: float | None = None
) -> None:
    """``setup_since``: when the login that led to the first enrolment happened."""
    request.session[KEY] = {
        "uid": str(user.pk),
        "mode": mode,
        "rule": rule,
        "setup_since": setup_since,
    }


def get(request, user) -> dict | None:
    data = request.session.get(KEY)
    if not isinstance(data, dict) or data.get("uid") != str(user.pk):
        return None
    return data


def in_setup_grace(request, user) -> bool:
    """Whether this session's first-enrolment login is recent (ADMIN_MFA_SETUP_GRACE)."""
    data = get(request, user)
    since = data.get("setup_since") if data else None
    if not isinstance(since, (int, float)):
        return False
    return 0 <= time.time() - since < conf.setup_grace()
