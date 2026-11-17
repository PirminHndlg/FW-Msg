"""The login policy end to end, through allauth's real views."""

from io import StringIO

import pytest
from allauth.mfa.models import Authenticator
from allauth.mfa.totp.internal.auth import TOTP, format_hotp_value, generate_totp_secret, hotp_value
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command
from django.test import override_settings
from django.urls import reverse

from admin_mfa import session

OFFICE = "192.0.2.0/24"
OFFICE_IP = "192.0.2.50"
REMOTE_IP = "198.51.100.7"
OUTSIDE_IP = "203.0.113.9"
NETWORKS = f"{OFFICE}; {REMOTE_IP}/32=alice"

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _clear_cache():
    # Rate limits and used TOTP codes live in the cache.
    cache.clear()
    yield
    cache.clear()


def make_user(username="staff", *, staff=True, superuser=False):
    return get_user_model().objects.create_user(
        username, password="pw", is_staff=staff or superuser, is_superuser=superuser
    )


def add_totp(user) -> str:
    secret = generate_totp_secret()
    TOTP.activate(user, secret)
    return secret


def totp_code(secret, offset=0) -> str:
    import time

    return format_hotp_value(hotp_value(secret, int(time.time()) // 30 + offset))


def login(client, ip, username="staff", password="pw"):
    return client.post(
        reverse("account_login"),
        {"login": username, "password": password},
        REMOTE_ADDR=ip,
    )


def get_admin(client, ip):
    return client.get("/admin/", REMOTE_ADDR=ip)


def record(client):
    return client.session.get(session.KEY)


def enter_code(client, secret, ip, *, trust=False):
    """The 2FA prompt, then allauth's trust-this-browser question."""
    response = client.post(reverse("mfa_authenticate"), {"code": totp_code(secret)}, REMOTE_ADDR=ip)
    if response.status_code == 302 and response["Location"] == reverse("mfa_trust"):
        response = client.post(
            reverse("mfa_trust"), {"action": "trust" if trust else "skip"}, REMOTE_ADDR=ip
        )
    return response


def reauthenticate(client, ip):
    """allauth asks for the password again before any change to the 2FA setup."""
    response = client.post(reverse("account_reauthenticate"), {"password": "pw"}, REMOTE_ADDR=ip)
    assert response.status_code == 302, response.content


# --- the admin is behind allauth -------------------------------------------


def test_admin_login_redirects_to_allauth(client):
    response = client.get("/admin/login/?next=/admin/", REMOTE_ADDR=OUTSIDE_IP)
    assert response.status_code == 302
    assert response["Location"].startswith(reverse("account_login"))


@pytest.mark.parametrize(
    "path",
    ["/auth/signup/", "/auth/password/reset/", "/auth/email/", "/auth/login/code/", "/auth/password/change/"],
)
def test_unused_allauth_pages_are_gone(client, path):
    assert client.get(path, REMOTE_ADDR=OUTSIDE_IP).status_code == 404


def test_login_page_has_no_signup_or_reset_link(client):
    response = client.get(reverse("account_login"), REMOTE_ADDR=OUTSIDE_IP)
    assert response.status_code == 200
    body = response.content.decode()
    assert "/auth/signup/" not in body
    assert "/auth/password/reset/" not in body
    assert "passkey" in body


def test_login_page_offers_saved_passkeys_in_the_username_field(client):
    body = client.get(reverse("account_login"), REMOTE_ADDR=OUTSIDE_IP).content.decode()
    assert 'autocomplete="username webauthn"' in body
    assert "autofocus" in body
    assert "admin_mfa/js/passkey-autofill.js" in body
    # The script drives allauth's passkey login form.
    assert 'id="mfa_login"' in body
    assert 'id="mfa_credential"' in body


@override_settings(ADMIN_MFA_TRUSTED_NETWORKS=NETWORKS)
def test_new_passkey_is_passwordless_by_default(client):
    make_user()
    login(client, OUTSIDE_IP)
    reauthenticate(client, OUTSIDE_IP)
    response = client.get(reverse("mfa_add_webauthn"), REMOTE_ADDR=OUTSIDE_IP)
    assert response.status_code == 200
    field = response.context["form"]["passwordless"]
    assert field.value() is True
    assert "checked" in str(field)


# --- outside, with a second factor -------------------------------------------


@override_settings(ADMIN_MFA_TRUSTED_NETWORKS=NETWORKS)
def test_outside_needs_second_factor(client):
    secret = add_totp(make_user())
    response = login(client, OUTSIDE_IP)
    assert response["Location"] == reverse("mfa_authenticate")
    # Not logged in until the code is in.
    assert get_admin(client, OUTSIDE_IP).status_code == 302
    response = enter_code(client, secret, OUTSIDE_IP)
    assert response.status_code == 302
    assert record(client)["mode"] == session.MODE_MFA
    assert get_admin(client, OUTSIDE_IP).status_code == 200
    # An MFA session may move between networks.
    assert get_admin(client, "198.51.100.1").status_code == 200


@override_settings(ADMIN_MFA_TRUSTED_NETWORKS=NETWORKS)
def test_wrong_code_does_not_log_in(client):
    add_totp(make_user())
    login(client, OUTSIDE_IP)
    response = client.post(reverse("mfa_authenticate"), {"code": "000000"}, REMOTE_ADDR=OUTSIDE_IP)
    assert response.status_code == 200
    assert get_admin(client, OUTSIDE_IP).status_code == 302


@override_settings(ADMIN_MFA_TRUSTED_NETWORKS=NETWORKS)
def test_abandoned_second_factor_cannot_be_completed_elsewhere(client):
    """Password at allauth, then skip the code by a site's own password-only login."""
    add_totp(make_user())
    login(client, OUTSIDE_IP)
    response = client.post(
        reverse("plain_login"), {"username": "staff", "password": "pw"}, REMOTE_ADDR=OUTSIDE_IP
    )
    assert response.status_code == 302  # Django's LoginView did log in ...
    response = get_admin(client, OUTSIDE_IP)
    assert response.status_code == 302  # ... but the session is not accepted
    assert response["Location"].startswith(reverse("account_login"))
    assert "_auth_user_id" not in client.session


def test_session_from_elsewhere_is_not_accepted(client):
    client.force_login(make_user())
    response = get_admin(client, OFFICE_IP)
    assert response.status_code == 302
    assert "_auth_user_id" not in client.session


@override_settings(ADMIN_MFA_ENFORCE=False)
def test_enforce_off_accepts_force_login(client):
    client.force_login(make_user())
    assert get_admin(client, OUTSIDE_IP).status_code == 200


# --- trusted networks -------------------------------------------------------


@override_settings(ADMIN_MFA_TRUSTED_NETWORKS=NETWORKS)
def test_office_skips_second_factor(client):
    add_totp(make_user())
    response = login(client, OFFICE_IP)
    assert response.status_code == 302
    assert response["Location"] != reverse("mfa_authenticate")
    assert record(client) == {"uid": str(get_user_model().objects.get().pk), "mode": "trusted", "rule": OFFICE, "setup_since": None}
    assert get_admin(client, OFFICE_IP).status_code == 200


@override_settings(ADMIN_MFA_TRUSTED_NETWORKS=NETWORKS)
def test_office_without_any_second_factor(client):
    make_user()
    login(client, OFFICE_IP)
    assert get_admin(client, OFFICE_IP).status_code == 200


@override_settings(ADMIN_MFA_TRUSTED_NETWORKS=NETWORKS)
def test_trusted_session_ends_off_network(client):
    make_user()
    login(client, OFFICE_IP)
    assert get_admin(client, OFFICE_IP).status_code == 200
    response = get_admin(client, OUTSIDE_IP)
    assert response.status_code == 302
    assert response["Location"].startswith(reverse("account_login"))
    assert get_admin(client, OFFICE_IP).status_code == 302  # stays logged out


@override_settings(ADMIN_MFA_TRUSTED_NETWORKS=NETWORKS)
def test_user_bound_rule(client):
    make_user("alice")
    add_totp(make_user("other"))
    response = login(client, REMOTE_IP, "alice")
    assert record(client)["rule"] == f"{REMOTE_IP}/32=alice"
    client.logout()
    response = login(client, REMOTE_IP, "other")
    assert response["Location"] == reverse("mfa_authenticate")


@override_settings(ADMIN_MFA_TRUSTED_NETWORKS=NETWORKS)
def test_superuser_needs_second_factor_in_the_office(client):
    add_totp(make_user("root", superuser=True))
    response = login(client, OFFICE_IP, "root")
    assert response["Location"] == reverse("mfa_authenticate")


@override_settings(ADMIN_MFA_TRUSTED_NETWORKS=NETWORKS, ADMIN_MFA_SUPERUSER_ALWAYS=False)
def test_superuser_rule_can_be_relaxed(client):
    add_totp(make_user("root", superuser=True))
    login(client, OFFICE_IP, "root")
    assert record(client)["mode"] == session.MODE_TRUSTED


@override_settings(ADMIN_MFA_TRUSTED_NETWORKS=NETWORKS, ALLAUTH_TRUSTED_PROXY_COUNT=1)
def test_forged_forwarded_for_is_ignored(client):
    """Caddy appends the real client IP; whatever the client sent comes first."""
    add_totp(make_user())
    response = client.post(
        reverse("account_login"),
        {"login": "staff", "password": "pw"},
        REMOTE_ADDR="10.0.0.1",  # the proxy
        HTTP_X_FORWARDED_FOR=f"{OFFICE_IP}, {OUTSIDE_IP}",
    )
    assert response["Location"] == reverse("mfa_authenticate")


@override_settings(ADMIN_MFA_TRUSTED_NETWORKS=NETWORKS, ALLAUTH_TRUSTED_PROXY_COUNT=1)
def test_forwarded_for_from_the_office(client):
    make_user()
    client.post(
        reverse("account_login"),
        {"login": "staff", "password": "pw"},
        REMOTE_ADDR="10.0.0.1",
        HTTP_X_FORWARDED_FOR=OFFICE_IP,
    )
    assert record(client)["mode"] == session.MODE_TRUSTED


# --- first enrolment --------------------------------------------------------


def _activate_totp(client, ip):
    # No password prompt in between: the login has just asked for it.
    assert client.get(reverse("mfa_activate_totp"), REMOTE_ADDR=ip).status_code == 200
    secret = client.session["mfa.totp.secret"]
    return client.post(reverse("mfa_activate_totp"), {"code": totp_code(secret)}, REMOTE_ADDR=ip)


def test_enrolment_anywhere_leads_to_setup_only(client):
    make_user()
    login(client, OUTSIDE_IP)
    assert record(client)["mode"] == session.MODE_ENROL
    response = get_admin(client, OUTSIDE_IP)
    assert response.status_code == 302
    assert response["Location"] == reverse("mfa_index")
    assert client.get(reverse("mfa_index"), REMOTE_ADDR=OUTSIDE_IP).status_code == 200
    response = _activate_totp(client, OUTSIDE_IP)
    assert response.status_code == 302
    assert Authenticator.objects.filter(type=Authenticator.Type.TOTP).exists()
    assert get_admin(client, OUTSIDE_IP).status_code == 200
    assert record(client)["mode"] == session.MODE_MFA


def test_enrolment_shows_recovery_codes_without_password(client):
    make_user()
    login(client, OUTSIDE_IP)
    _activate_totp(client, OUTSIDE_IP)
    response = client.get(reverse("mfa_view_recovery_codes"), REMOTE_ADDR=OUTSIDE_IP)
    assert response.status_code == 200
    assert record(client)["mode"] == session.MODE_MFA


def test_enrolment_passkey_page_without_password(client):
    make_user()
    login(client, OUTSIDE_IP)
    response = client.get(reverse("mfa_add_webauthn"), REMOTE_ADDR=OUTSIDE_IP)
    assert response.status_code == 200


def _age_setup(client, seconds):
    s = client.session
    data = dict(s[session.KEY])
    data["setup_since"] -= seconds
    s[session.KEY] = data
    s.save()


def test_setup_grace_runs_out(client):
    make_user()
    login(client, OUTSIDE_IP)
    _age_setup(client, 901)
    response = client.get(reverse("mfa_activate_totp"), REMOTE_ADDR=OUTSIDE_IP)
    assert response.status_code == 302
    assert response["Location"].startswith(reverse("account_reauthenticate"))


@override_settings(ADMIN_MFA_SETUP_GRACE=0)
def test_setup_grace_can_be_turned_off(client):
    make_user()
    login(client, OUTSIDE_IP)
    response = client.get(reverse("mfa_activate_totp"), REMOTE_ADDR=OUTSIDE_IP)
    assert response["Location"].startswith(reverse("account_reauthenticate"))


@override_settings(ADMIN_MFA_TRUSTED_NETWORKS=NETWORKS, ADMIN_MFA_FIRST_ENROLMENT="trusted")
def test_enrolment_trusted_refuses_outside(client):
    make_user()
    response = login(client, OUTSIDE_IP)
    assert response["Location"] == reverse("account_login")
    assert "_auth_user_id" not in client.session
    page = client.get(reverse("account_login"), REMOTE_ADDR=OUTSIDE_IP).content.decode()
    assert "office network" in page


@override_settings(ADMIN_MFA_TRUSTED_NETWORKS=NETWORKS, ADMIN_MFA_FIRST_ENROLMENT="trusted")
def test_enrolment_trusted_allows_superuser_in_office(client):
    make_user("root", superuser=True)
    login(client, OFFICE_IP, "root")
    assert record(client)["mode"] == session.MODE_ENROL


# --- keeping a second factor ------------------------------------------------


def _mfa_login(client, secret, ip=OUTSIDE_IP):
    login(client, ip)
    enter_code(client, secret, ip)
    assert record(client)["mode"] == session.MODE_MFA
    reauthenticate(client, ip)


def test_login_with_second_factor_still_asks_for_password(client):
    user = make_user()
    secret = add_totp(user)
    login(client, OUTSIDE_IP)
    enter_code(client, secret, OUTSIDE_IP)
    assert record(client)["setup_since"] is None
    response = client.get(reverse("mfa_add_webauthn"), REMOTE_ADDR=OUTSIDE_IP)
    assert response["Location"].startswith(reverse("account_reauthenticate"))


def test_password_confirmation_names_the_user(client):
    user = make_user()
    secret = add_totp(user)
    login(client, OUTSIDE_IP)
    enter_code(client, secret, OUTSIDE_IP)
    page = client.get(reverse("account_reauthenticate"), REMOTE_ADDR=OUTSIDE_IP).content.decode()
    assert 'name="username" value="staff" autocomplete="username"' in page
    assert 'autocomplete="current-password"' in page


def test_failed_password_confirmation_is_logged_with_its_page(client, caplog):
    user = make_user()
    secret = add_totp(user)
    login(client, OUTSIDE_IP)
    enter_code(client, secret, OUTSIDE_IP)
    with caplog.at_level("INFO", logger="admin_mfa"):
        client.post(reverse("account_reauthenticate"), {"password": "nope"}, REMOTE_ADDR=OUTSIDE_IP)
    lines = [r.getMessage() for r in caplog.records if r.getMessage().startswith("login_failed")]
    assert lines and f"path={reverse('account_reauthenticate')}" in lines[0]


def test_last_totp_cannot_be_deactivated(client):
    user = make_user()
    secret = add_totp(user)
    _mfa_login(client, secret)
    response = client.post(reverse("mfa_deactivate_totp"), REMOTE_ADDR=OUTSIDE_IP)
    assert response.status_code == 200  # form error, nothing removed
    assert Authenticator.objects.filter(user=user, type=Authenticator.Type.TOTP).exists()


def test_last_passkey_cannot_be_removed(client):
    user = make_user()
    secret = add_totp(user)
    _mfa_login(client, secret)
    Authenticator.objects.filter(user=user, type=Authenticator.Type.TOTP).delete()
    passkey = Authenticator.objects.create(user=user, type=Authenticator.Type.WEBAUTHN, data={"name": "key"})
    response = client.post(
        reverse("mfa_remove_webauthn", kwargs={"pk": passkey.pk}), REMOTE_ADDR=OUTSIDE_IP
    )
    assert response.status_code == 302
    assert Authenticator.objects.filter(pk=passkey.pk).exists()


def test_non_staff_users_are_left_alone(client):
    make_user("customer", staff=False)
    response = login(client, OUTSIDE_IP, "customer")
    assert response.status_code == 302
    assert record(client) is None
    # They log in through the site's own login, which has no 2FA step: a
    # factor set up here would protect nothing, so the setup pages are closed.
    assert client.get(reverse("mfa_index"), REMOTE_ADDR=OUTSIDE_IP).status_code == 404
    assert client.get(reverse("mfa_activate_totp"), REMOTE_ADDR=OUTSIDE_IP).status_code == 404


def superusers_only(user):
    return user.is_superuser


@override_settings(ADMIN_MFA_APPLIES_TO="tests.test_flow.superusers_only")
def test_applies_to_narrows_the_policy(client):
    """A multi-tenant site: customers' own staff accounts keep their login."""
    make_user("customer-admin")  # staff, not superuser
    response = login(client, OUTSIDE_IP, "customer-admin")
    assert record(client) is None
    assert get_admin(client, OUTSIDE_IP).status_code == 200
    client.logout()
    make_user("root", superuser=True)
    login(client, OUTSIDE_IP, "root")
    assert record(client)["mode"] == session.MODE_ENROL
    assert get_admin(client, OUTSIDE_IP)["Location"] == reverse("mfa_index")


@override_settings(LOGIN_URL="/plain-login/")
def test_admin_login_ignores_the_sites_login_url(client):
    response = client.get("/admin/login/?next=/admin/", REMOTE_ADDR=OUTSIDE_IP)
    assert response["Location"].startswith(reverse("account_login"))
    assert "next=%2Fadmin%2F" in response["Location"]


@override_settings(LOGIN_URL="/plain-login/")
def test_ended_session_goes_to_the_2fa_login(client):
    client.force_login(make_user())
    response = get_admin(client, OUTSIDE_IP)
    assert response["Location"].startswith(reverse("account_login"))


# --- trust this browser -----------------------------------------------------


def test_trusted_browser_skips_code_next_time(client):
    secret = add_totp(make_user())
    login(client, OUTSIDE_IP)
    response = enter_code(client, secret, OUTSIDE_IP, trust=True)
    assert response.status_code == 302
    assert record(client)["mode"] == session.MODE_MFA
    client.post(reverse("account_logout"), REMOTE_ADDR=OUTSIDE_IP)
    response = login(client, OUTSIDE_IP)
    assert response["Location"] != reverse("mfa_authenticate")
    assert record(client)["mode"] == session.MODE_MFA
    assert get_admin(client, OUTSIDE_IP).status_code == 200


# --- reset command ----------------------------------------------------------


def test_reset_command(client):
    user = make_user()
    add_totp(user)
    out = StringIO()
    call_command("admin_mfa_reset", "staff", "--yes", stdout=out)
    assert "Removed" in out.getvalue()
    assert not Authenticator.objects.filter(user=user).exists()
