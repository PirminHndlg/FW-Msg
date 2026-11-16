"""Two-factor authentication in FWMsg, on top of ``admin_mfa`` (django-allauth MFA).

Who it applies to (``ADMIN_MFA_APPLIES_TO = "Home.mfa.applies_to"``):

* Admins (superuser, staff, role ``"A"``) must use a second factor. Their first
  login after the rollout leads to the setup page.
* Everyone else may turn it on in the settings (``Home.views.mfa_enable``).
  While the setup is pending, the user is in the ``OPT_IN_GROUP`` group; once
  a second factor exists, that alone keeps the policy on. Turning it off
  (``Home.views.mfa_disable``) removes the factors and the group.

For users the policy applies to, ``admin_mfa`` only accepts sessions written by
allauth's login flow; FWMsg's other ways into an account (token login, first
login with a one-time password) therefore send them to the login page instead.
"""

from __future__ import annotations

from allauth.mfa.models import Authenticator
from django.contrib import messages
from django.contrib.auth.models import Group
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.shortcuts import redirect
from django.utils.translation import gettext as _

from admin_mfa import adapters as admin_mfa_adapters
from admin_mfa import forms as admin_mfa_forms
from admin_mfa import policy

OPT_IN_GROUP = "Zwei-Faktor-Authentifizierung"
WEAK_PASSWORD_SESSION_KEY = "fwmsg_weak_password"


def _role(user):
    try:
        return user.role
    except Exception:  # noqa: BLE001 - users without CustomUser/person cluster
        return None


def mfa_required(user) -> bool:
    """Admins: they cannot turn MFA off."""
    return bool(user.is_superuser or user.is_staff or _role(user) == "A")


def opted_in(user) -> bool:
    return user.groups.filter(name=OPT_IN_GROUP).exists()


def applies_to(user) -> bool:
    return mfa_required(user) or policy.has_second_factor(user) or opted_in(user)


def opt_in(user) -> None:
    group, _created = Group.objects.get_or_create(name=OPT_IN_GROUP)
    user.groups.add(group)


def opt_out(user) -> None:
    """Remove all factors (incl. recovery codes) and the opt-in of a non-admin."""
    Authenticator.objects.filter(user=user).delete()
    user.groups.remove(*Group.objects.filter(name=OPT_IN_GROUP))


def _person_cluster_inactive_message(user) -> str | None:
    customuser = getattr(user, "customuser", None)
    if customuser is None or customuser.person_cluster is None:
        return None
    if customuser.person_cluster.active:
        return None
    message = _("Dein Account ist nicht aktiv.")
    org_mail = customuser.org.email if customuser.org else None
    if org_mail:
        message += "\n\n" + _("Melde dich bei %(email)s um deinen Account zu aktivieren.") % {
            "email": org_mail
        }
    else:
        message += "\n\n" + _("Melde dich beim Administrator um deinen Account zu aktivieren.")
    return message


class AccountAdapter(admin_mfa_adapters.AccountAdapter):
    def pre_login(self, request, user, **kwargs):
        message = _person_cluster_inactive_message(user)
        if message:
            from allauth.account.internal.stagekit import clear_login

            clear_login(request)
            messages.error(request, message)
            return redirect("index")
        # An opt-in that was never finished (no factor set up) does not force
        # the setup at the next login: the user simply has no MFA.
        if not mfa_required(user) and opted_in(user) and not policy.has_second_factor(user):
            user.groups.remove(*Group.objects.filter(name=OPT_IN_GROUP))
        return super().pre_login(request, user, **kwargs)

    def get_login_redirect_url(self, request):
        if request.session.pop(WEAK_PASSWORD_SESSION_KEY, False):
            messages.error(
                request,
                _("Das Passwort entspricht den Anforderungen nicht, wir empfehlen einen Passwortwechsel."),
            )
            return "/password_change"
        return super().get_login_redirect_url(request)

    def add_message(self, request, level, message_template=None, message_context=None, extra_tags="", message=None):
        # FWMsg shows its own messages; allauth's "Successfully signed in as …"
        # would only clutter the start page.
        if message_template in ("account/messages/logged_in.txt", "account/messages/logged_out.txt"):
            return
        super().add_message(request, level, message_template, message_context, extra_tags, message)


class LoginForm(admin_mfa_forms.LoginForm):
    """allauth's login form (username or e-mail) in FWMsg's look.

    Also remembers whether the password meets the current requirements, so
    that the redirect after the login (which may come after the second factor)
    can recommend changing it, as FWMsg's login did before.
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.fields["login"].label = _("Benutzername oder E-Mail")
        self.fields["password"].label = _("Passwort")
        for name in ("login", "password"):
            widget = self.fields[name].widget
            widget.attrs["class"] = "form-control rounded-3"
            widget.attrs["placeholder"] = self.fields[name].label

    def clean(self):
        cleaned_data = super().clean()
        if self.user is not None and self.request is not None:
            try:
                validate_password(cleaned_data.get("password", ""), self.user)
            except ValidationError:
                self.request.session[WEAK_PASSWORD_SESSION_KEY] = True
        return cleaned_data
