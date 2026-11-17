"""What admin_mfa relies on in allauth's internals. Fails first on an upgrade."""

from allauth.account.adapter import get_adapter
from allauth.account.stages import LoginStageController
from allauth.mfa.stages import AuthenticateStage as AllauthAuthenticateStage
from django.contrib import admin
from django.test import RequestFactory

from admin_mfa.stages import AuthenticateStage, FinalizeStage


def test_stage_list_replaces_mfa_stage_and_finalizes_last():
    stages = get_adapter().get_login_stages()
    assert "allauth.mfa.stages.AuthenticateStage" not in stages
    assert "admin_mfa.stages.AuthenticateStage" in stages
    assert stages[-1] == "admin_mfa.stages.FinalizeStage"
    assert stages.index("admin_mfa.stages.AuthenticateStage") < stages.index("allauth.mfa.stages.TrustStage") if "allauth.mfa.stages.TrustStage" in stages else True


def test_stage_keeps_allauths_key_and_url():
    # allauth's 2FA view finds its stage by this key.
    assert AuthenticateStage.key == AllauthAuthenticateStage.key
    assert AuthenticateStage.urlname == "mfa_authenticate"
    assert FinalizeStage.key not in {AllauthAuthenticateStage.key}


def test_controller_api_used_by_finalize_stage():
    assert hasattr(LoginStageController, "get_stage")


def test_default_admin_site_is_protected():
    assert getattr(admin.site.login, "_admin_mfa_protected", False)


def test_client_ip_comes_from_adapter():
    request = RequestFactory().get("/", REMOTE_ADDR="192.0.2.7")
    assert get_adapter(request).get_client_ip(request) == "192.0.2.7"
