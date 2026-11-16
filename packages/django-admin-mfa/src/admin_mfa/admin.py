from functools import wraps

from django.contrib.auth import REDIRECT_FIELD_NAME
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseRedirect
from django.shortcuts import resolve_url
from django.utils.http import urlencode

from . import conf


def protect(site) -> None:
    """Send ``site``'s login to the 2FA login (``ADMIN_MFA_LOGIN_URL``). Idempotent.

    allauth's ``secure_admin_login`` does the same but goes to ``LOGIN_URL``,
    which a site may keep for its own login page.
    """
    if getattr(site.login, "_admin_mfa_protected", False):
        return
    view = site.login

    @wraps(view)
    def login(request, *args, **kwargs):
        if request.user.is_authenticated:
            if not request.user.is_staff or not request.user.is_active:
                raise PermissionDenied
            return view(request, *args, **kwargs)
        next_url = request.GET.get(REDIRECT_FIELD_NAME) or request.get_full_path()
        url = resolve_url(conf.login_url())
        return HttpResponseRedirect(f"{url}?{urlencode({REDIRECT_FIELD_NAME: next_url})}")

    login._admin_mfa_protected = True
    site.login = login
