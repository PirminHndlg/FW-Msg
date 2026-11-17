"""Settings of admin_mfa, and ``configure()`` to wire allauth into a site.

Site settings (all optional):

``ADMIN_MFA_TRUSTED_NETWORKS``
    Networks whose logins skip the second factor. A string (env-file
    friendly) or a list of entries. An entry is ``cidr`` (any staff user) or
    ``cidr=user1,user2`` (only these usernames). Entries in a string are
    separated by ``;`` or newlines::

        192.0.2.0/24; 198.51.100.7/32=alice

    Default: none — every staff login needs the second factor.

``ADMIN_MFA_SUPERUSER_ALWAYS``
    Superusers need the second factor on trusted networks too. Default True.

``ADMIN_MFA_FIRST_ENROLMENT``
    Where a staff user without a second factor may log in to set one up:
    ``"anywhere"`` (default; the first login after the rollout leads straight
    to the setup page) or ``"trusted"`` (only from a trusted network; logins
    from elsewhere are refused until the user has set one up).

``ADMIN_MFA_ENFORCE``
    The middleware's session checks. Default True. Test settings of a site
    may turn it off, so that ``Client.force_login`` keeps working there.

``ADMIN_MFA_APPLIES_TO``
    Dotted path to a callable ``(user) -> bool``: the users the policy is
    for. Default ``admin_mfa.policy.staff_or_superuser``. A multi-tenant site
    can narrow it, e.g. to its own operators' accounts; everyone else keeps
    the site's own login and never reaches the 2FA setup pages.

``ADMIN_MFA_LOGIN_URL``
    Where the admin's login and an ended session send the browser: the 2FA
    login. Default ``"account_login"``. Independent of ``LOGIN_URL``, which a
    site may keep pointing at its own login page for its other users.

``ADMIN_MFA_SETUP_GRACE``
    Seconds after a first-enrolment login during which changes to the 2FA
    setup do not ask for the password again (allauth's reauthentication).
    The user has just typed it, and an enrolment session reaches nothing but
    the setup pages. Default 900. Afterwards, and for every login that
    already had a second factor, allauth asks as usual.
"""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

FIRST_ENROLMENT_CHOICES = ("anywhere", "trusted")


@dataclass(frozen=True)
class TrustedNetwork:
    network: ipaddress.IPv4Network | ipaddress.IPv6Network
    usernames: frozenset[str] = frozenset()

    def matches(self, ip: str | None, username: str) -> bool:
        if not ip:
            return False
        try:
            address = ipaddress.ip_address(ip)
        except ValueError:
            return False
        if address.version != self.network.version or address not in self.network:
            return False
        return not self.usernames or username in self.usernames

    def __str__(self) -> str:
        if self.usernames:
            return f"{self.network}={','.join(sorted(self.usernames))}"
        return str(self.network)


def parse_trusted_networks(value) -> tuple[TrustedNetwork, ...]:
    if not value:
        return ()
    if isinstance(value, str):
        entries = value.replace("\n", ";").split(";")
    else:
        entries = list(value)
    rules = []
    for raw in entries:
        entry = str(raw).strip()
        if not entry:
            continue
        cidr, sep, users = entry.partition("=")
        try:
            # strict: 192.0.2.1/24 is a typo for either the host or the net.
            network = ipaddress.ip_network(cidr.strip(), strict=True)
        except ValueError as e:
            raise ImproperlyConfigured(
                f"ADMIN_MFA_TRUSTED_NETWORKS: {entry!r} is not a network ({e})"
            ) from e
        usernames = frozenset(u.strip() for u in users.split(",") if u.strip())
        if sep and not usernames:
            raise ImproperlyConfigured(
                f"ADMIN_MFA_TRUSTED_NETWORKS: {entry!r} names no user after '='"
            )
        rules.append(TrustedNetwork(network, usernames))
    return tuple(rules)


def trusted_networks() -> tuple[TrustedNetwork, ...]:
    return parse_trusted_networks(getattr(settings, "ADMIN_MFA_TRUSTED_NETWORKS", None))


def superuser_always() -> bool:
    return bool(getattr(settings, "ADMIN_MFA_SUPERUSER_ALWAYS", True))


def first_enrolment() -> str:
    value = getattr(settings, "ADMIN_MFA_FIRST_ENROLMENT", "anywhere")
    if value not in FIRST_ENROLMENT_CHOICES:
        raise ImproperlyConfigured(
            f"ADMIN_MFA_FIRST_ENROLMENT must be one of {FIRST_ENROLMENT_CHOICES}, not {value!r}"
        )
    return value


def enforce() -> bool:
    return bool(getattr(settings, "ADMIN_MFA_ENFORCE", True))


def setup_grace() -> int:
    return int(getattr(settings, "ADMIN_MFA_SETUP_GRACE", 900))


def login_url() -> str:
    return getattr(settings, "ADMIN_MFA_LOGIN_URL", "account_login")


def applies_to_path() -> str:
    return getattr(settings, "ADMIN_MFA_APPLIES_TO", "admin_mfa.policy.staff_or_superuser")


_AUTH_MIDDLEWARE = "django.contrib.auth.middleware.AuthenticationMiddleware"
_MESSAGE_MIDDLEWARE = "django.contrib.messages.middleware.MessageMiddleware"


def configure(
    g: dict,
    *,
    site_name: str,
    trusted_proxy_count: int,
    trusted_networks: str | list | None = None,
    first_enrolment: str = "anywhere",
) -> None:
    """Add allauth + admin_mfa to a settings module: ``configure(globals(), ...)``.

    ``site_name`` labels the TOTP entry in authenticator apps.
    ``trusted_proxy_count`` is the number of reverse proxies in front of the
    app that append to X-Forwarded-For (1 for a single Caddy). It decides
    which client IP the trusted-network rules see; 0 uses REMOTE_ADDR.

    Values the settings module already set are kept, so a site can override
    any of them by assigning before the call.
    """
    apps = list(g.get("INSTALLED_APPS", []))
    # admin_mfa first: its templates override allauth's.
    for app in ("admin_mfa", "allauth", "allauth.account", "allauth.mfa"):
        if app not in apps:
            if app == "admin_mfa":
                apps.insert(0, app)
            else:
                apps.append(app)
    g["INSTALLED_APPS"] = apps

    middleware = list(g.get("MIDDLEWARE", []))
    if _AUTH_MIDDLEWARE not in middleware:
        raise ImproperlyConfigured(f"admin_mfa needs {_AUTH_MIDDLEWARE} in MIDDLEWARE")
    anchor = _MESSAGE_MIDDLEWARE if _MESSAGE_MIDDLEWARE in middleware else _AUTH_MIDDLEWARE
    pos = middleware.index(anchor) + 1
    for mw in ("allauth.account.middleware.AccountMiddleware", "admin_mfa.middleware.AdminMFAMiddleware"):
        if mw not in middleware:
            middleware.insert(pos, mw)
            pos += 1
    g["MIDDLEWARE"] = middleware

    backends = list(g.get("AUTHENTICATION_BACKENDS", ["django.contrib.auth.backends.ModelBackend"]))
    if "allauth.account.auth_backends.AuthenticationBackend" not in backends:
        backends.append("allauth.account.auth_backends.AuthenticationBackend")
    g["AUTHENTICATION_BACKENDS"] = backends

    defaults = {
        "LOGIN_URL": "account_login",
        "LOGIN_REDIRECT_URL": "admin:index",
        "ACCOUNT_LOGOUT_REDIRECT_URL": "account_login",
        "ACCOUNT_ADAPTER": "admin_mfa.adapters.AccountAdapter",
        "ACCOUNT_LOGIN_METHODS": {"username"},
        "ACCOUNT_SIGNUP_FIELDS": ["username*", "password1*"],
        "ACCOUNT_EMAIL_VERIFICATION": "none",
        "ACCOUNT_SESSION_REMEMBER": None,
        "MFA_ADAPTER": "admin_mfa.adapters.MFAAdapter",
        "MFA_SUPPORTED_TYPES": ["webauthn", "totp", "recovery_codes"],
        "MFA_PASSKEY_LOGIN_ENABLED": True,
        "MFA_TRUST_ENABLED": True,
        "MFA_TRUST_COOKIE_AGE": timedelta(days=30),
        "MFA_TOTP_ISSUER": site_name,
        "ALLAUTH_TRUSTED_PROXY_COUNT": trusted_proxy_count,
        "ADMIN_MFA_TRUSTED_NETWORKS": trusted_networks or "",
        "ADMIN_MFA_FIRST_ENROLMENT": first_enrolment,
    }
    for key, value in defaults.items():
        g.setdefault(key, value)

    # Per form, so a site that replaces one of allauth's forms keeps ours for
    # the others.
    g["ACCOUNT_FORMS"] = {"login": "admin_mfa.forms.LoginForm", **g.get("ACCOUNT_FORMS", {})}
    g["MFA_FORMS"] = {"add_webauthn": "admin_mfa.forms.AddWebAuthnForm", **g.get("MFA_FORMS", {})}

    # Fail at startup, not at the first login.
    parse_trusted_networks(g["ADMIN_MFA_TRUSTED_NETWORKS"])
    if g["ADMIN_MFA_FIRST_ENROLMENT"] not in FIRST_ENROLMENT_CHOICES:
        raise ImproperlyConfigured(f"ADMIN_MFA_FIRST_ENROLMENT: {g['ADMIN_MFA_FIRST_ENROLMENT']!r}")
