"""One log line per security-relevant event, on the ``admin_mfa`` logger."""

from __future__ import annotations

import logging

from allauth.mfa import signals as mfa_signals
from django.contrib.auth import signals as auth_signals

logger = logging.getLogger("admin_mfa")


def _ip(request) -> str:
    if request is None:
        return "-"
    from .policy import client_ip

    try:
        return client_ip(request)
    except Exception:  # noqa: BLE001 - logging must not break a login
        return request.META.get("REMOTE_ADDR", "-")


def _ua(request) -> str:
    if request is None:
        return "-"
    return request.META.get("HTTP_USER_AGENT", "-")[:200]


def event(name: str, request, user=None, **fields) -> None:
    username = user.get_username() if user is not None else fields.pop("username", "-")
    extra = " ".join(f"{k}={v}" for k, v in fields.items() if v is not None)
    logger.info(
        "%s user=%s ip=%s %s ua=%r", name, username, _ip(request), extra, _ua(request)
    )


def _on_login_failed(sender, credentials, request=None, **kwargs):
    # path: the login page or allauth's password confirmation (reauthenticate)
    path = request.path if request is not None else None
    event("login_failed", request, username=credentials.get("username", "-"), path=path)


def _on_authenticator_added(sender, request, user, authenticator, **kwargs):
    event("authenticator_added", request, user, type=authenticator.type)


def _on_authenticator_removed(sender, request, user, authenticator, **kwargs):
    event("authenticator_removed", request, user, type=authenticator.type)


def _on_authenticator_reset(sender, request, user, authenticator, **kwargs):
    event("authenticator_reset", request, user, type=authenticator.type)


def connect() -> None:
    auth_signals.user_login_failed.connect(_on_login_failed, dispatch_uid="admin_mfa.login_failed")
    mfa_signals.authenticator_added.connect(_on_authenticator_added, dispatch_uid="admin_mfa.added")
    mfa_signals.authenticator_removed.connect(_on_authenticator_removed, dispatch_uid="admin_mfa.removed")
    mfa_signals.authenticator_reset.connect(_on_authenticator_reset, dispatch_uid="admin_mfa.reset")
