import pytest
from django.core.exceptions import ImproperlyConfigured

from admin_mfa.conf import configure, parse_trusted_networks


def test_parse_string_with_user_rule():
    rules = parse_trusted_networks("192.0.2.0/24; 198.51.100.7/32=alice, anna\n2001:db8::/32")
    assert [str(r) for r in rules] == ["192.0.2.0/24", "198.51.100.7/32=alice,anna", "2001:db8::/32"]
    office, airport, v6 = rules
    assert office.matches("192.0.2.77", "anyone")
    assert not office.matches("192.0.3.1", "anyone")
    assert airport.matches("198.51.100.7", "alice")
    assert not airport.matches("198.51.100.7", "someone-else")
    assert v6.matches("2001:db8::1", "x")
    assert not v6.matches("192.0.2.1", "x")


@pytest.mark.parametrize("value", [None, "", " ; ", []])
def test_parse_empty(value):
    assert parse_trusted_networks(value) == ()


@pytest.mark.parametrize("value", ["192.0.2.1/24", "not-an-ip", "10.0.0.0/8="])
def test_parse_rejects_typos(value):
    with pytest.raises(ImproperlyConfigured):
        parse_trusted_networks(value)


def test_matches_rejects_garbage_ip():
    (rule,) = parse_trusted_networks("10.0.0.0/8")
    assert not rule.matches(None, "x")
    assert not rule.matches("unknown", "x")


def _settings():
    return {
        "INSTALLED_APPS": ["django.contrib.admin", "django.contrib.auth"],
        "MIDDLEWARE": [
            "django.contrib.sessions.middleware.SessionMiddleware",
            "django.contrib.auth.middleware.AuthenticationMiddleware",
            "django.contrib.messages.middleware.MessageMiddleware",
            "x.Last",
        ],
    }


def test_configure_wires_apps_middleware_and_defaults():
    g = _settings()
    configure(g, site_name="Passar", trusted_proxy_count=1, trusted_networks="192.0.2.0/24")
    assert g["INSTALLED_APPS"][0] == "admin_mfa"
    assert g["INSTALLED_APPS"][-3:] == ["allauth", "allauth.account", "allauth.mfa"]
    assert g["MIDDLEWARE"] == [
        "django.contrib.sessions.middleware.SessionMiddleware",
        "django.contrib.auth.middleware.AuthenticationMiddleware",
        "django.contrib.messages.middleware.MessageMiddleware",
        "allauth.account.middleware.AccountMiddleware",
        "admin_mfa.middleware.AdminMFAMiddleware",
        "x.Last",
    ]
    assert g["AUTHENTICATION_BACKENDS"][-1] == "allauth.account.auth_backends.AuthenticationBackend"
    assert g["ALLAUTH_TRUSTED_PROXY_COUNT"] == 1
    assert g["MFA_TOTP_ISSUER"] == "Passar"
    assert g["LOGIN_URL"] == "account_login"


def test_configure_is_idempotent_and_keeps_site_values():
    g = _settings()
    g["LOGIN_REDIRECT_URL"] = "/somewhere/"
    configure(g, site_name="A", trusted_proxy_count=0)
    configure(g, site_name="B", trusted_proxy_count=1)
    assert g["INSTALLED_APPS"].count("allauth") == 1
    assert g["MIDDLEWARE"].count("admin_mfa.middleware.AdminMFAMiddleware") == 1
    assert g["LOGIN_REDIRECT_URL"] == "/somewhere/"
    assert g["MFA_TOTP_ISSUER"] == "A"


def test_configure_fails_early_on_bad_networks():
    with pytest.raises(ImproperlyConfigured):
        configure(_settings(), site_name="A", trusted_proxy_count=0, trusted_networks="10.0.0.1/8")


def test_configure_installs_its_forms_next_to_the_sites_own():
    g = _settings()
    g["ACCOUNT_FORMS"] = {"signup": "site.forms.Signup"}
    g["MFA_FORMS"] = {"add_webauthn": "site.forms.AddPasskey"}
    configure(g, site_name="A", trusted_proxy_count=0)
    assert g["ACCOUNT_FORMS"] == {"login": "admin_mfa.forms.LoginForm", "signup": "site.forms.Signup"}
    assert g["MFA_FORMS"] == {"add_webauthn": "site.forms.AddPasskey"}
