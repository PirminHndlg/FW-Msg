"""Two-factor authentication in FWMsg (Home/mfa.py on top of packages/django-admin-mfa)."""

import time
from unittest.mock import patch

from allauth.mfa.models import Authenticator
from allauth.mfa.recovery_codes.internal.auth import RecoveryCodes
from allauth.mfa.totp.internal.auth import TOTP, format_hotp_value, generate_totp_secret, hotp_value
from django.contrib.auth.models import Group, User
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from Global.models import CustomUser, PersonCluster
from ORG.models import Organisation

from . import mfa

PASSWORD = 'Sicheres-Test-Passwort-2026!'


def add_totp(user) -> str:
    secret = generate_totp_secret()
    TOTP.activate(user, secret)
    return secret


def totp_code(secret: str) -> str:
    return format_hotp_value(hotp_value(secret, int(time.time()) // 30))


@override_settings(ADMIN_MFA_ENFORCE=True)
class MFATestCase(TestCase):
    def setUp(self):
        # Rate limits and used TOTP codes live in the cache.
        cache.clear()
        with patch('ORG.tasks.send_register_email_task'):
            self.org = Organisation.objects.create(name='MFA test org', email='org@example.com')
        self.cluster = PersonCluster.objects.create(org=self.org, name='Freiwillige', view='F', active=True)
        self.volunteer = self.make_user('freiwillig', self.cluster, email='fw@example.com')
        admin_cluster = PersonCluster.objects.create(org=self.org, name='Admins', view='A', active=True)
        self.admin = self.make_user('admin', admin_cluster)

    def make_user(self, username, cluster, email=''):
        user = User.objects.create_user(username=username, email=email, password=PASSWORD)
        CustomUser.objects.create(user=user, org=self.org, person_cluster=cluster)
        return User.objects.get(pk=user.pk)

    def login(self, login, password=PASSWORD):
        return self.client.post(reverse('account_login'), {'login': login, 'password': password})

    def enter_code(self, secret):
        """The 2FA prompt, then allauth's "trust this browser?" question."""
        response = self.client.post(reverse('mfa_authenticate'), {'code': totp_code(secret)})
        if response.status_code == 302 and response['Location'] == reverse('mfa_trust'):
            response = self.client.post(reverse('mfa_trust'), {'action': 'skip'})
        return response

    def assert_logged_in_as(self, user):
        self.assertEqual(self.client.session.get('_auth_user_id'), str(user.pk))

    def assert_logged_out(self):
        self.assertNotIn('_auth_user_id', self.client.session)


class LoginPageTests(MFATestCase):
    def test_start_page_shows_login_form(self):
        response = self.client.get(reverse('index_home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="login"')
        self.assertContains(response, 'id="passkey_login"')

    def test_login_url_shows_login_form(self):
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="password"')

    def test_volunteer_logs_in_with_password_only(self):
        response = self.login('freiwillig')
        self.assert_logged_in_as(self.volunteer)
        self.assertRedirects(response, '/', fetch_redirect_response=False)
        self.assertRedirects(self.client.get('/'), reverse('fw_home'), fetch_redirect_response=False)

    def test_login_with_email(self):
        self.login('fw@example.com')
        self.assert_logged_in_as(self.volunteer)

    def test_wrong_password_is_refused(self):
        response = self.login('freiwillig', 'falsch')
        self.assertEqual(response.status_code, 200)
        self.assert_logged_out()

    def test_inactive_person_cluster_is_refused(self):
        self.cluster.active = False
        self.cluster.save()
        response = self.login('freiwillig')
        self.assert_logged_out()
        self.assertRedirects(response, reverse('index'), fetch_redirect_response=False)

    def test_weak_password_recommends_change(self):
        self.volunteer.set_password('abc')
        self.volunteer.save()
        response = self.login('freiwillig', 'abc')
        self.assert_logged_in_as(self.volunteer)
        self.assertRedirects(response, reverse('password_change'), fetch_redirect_response=False)


class AdminMFATests(MFATestCase):
    def test_admin_roles_require_mfa(self):
        self.assertTrue(mfa.mfa_required(self.admin))
        self.assertTrue(mfa.mfa_required(User(is_superuser=True)))
        self.assertTrue(mfa.mfa_required(User(is_staff=True)))
        self.assertFalse(mfa.mfa_required(self.volunteer))

    def test_admin_without_factor_is_sent_to_setup(self):
        self.login('admin')
        self.assert_logged_in_as(self.admin)
        response = self.client.get(reverse('admin_home'))
        self.assertRedirects(response, reverse('mfa_index'), fetch_redirect_response=False)

    def test_admin_with_totp_needs_code(self):
        secret = add_totp(self.admin)
        response = self.login('admin')
        self.assertRedirects(response, reverse('mfa_authenticate'), fetch_redirect_response=False)
        self.assert_logged_out()

        self.enter_code(secret)
        self.assert_logged_in_as(self.admin)
        response = self.client.get(reverse('admin_home'))
        self.assertNotEqual(response.get('Location'), reverse('mfa_index'))

    def test_session_without_mfa_login_is_ended(self):
        add_totp(self.admin)
        self.client.force_login(self.admin)
        self.client.get(reverse('admin_home'))
        self.assert_logged_out()

    def test_admin_cannot_disable_mfa(self):
        secret = add_totp(self.admin)
        self.login('admin')
        self.enter_code(secret)
        self.client.post(reverse('mfa_disable'))
        self.assertTrue(Authenticator.objects.filter(user=self.admin).exists())

    def test_token_login_does_not_skip_second_factor(self):
        add_totp(self.admin)
        self.admin.customuser.create_token()
        token = self.admin.customuser.token
        response = self.client.get(reverse('token_login', args=[token]))
        self.assertRedirects(response, reverse('login'), fetch_redirect_response=False)
        self.assert_logged_out()

    def test_password_change_keeps_mfa_session(self):
        secret = add_totp(self.admin)
        self.login('admin')
        self.enter_code(secret)
        new_password = 'Noch-sichereres-Passwort-2026!'
        self.client.post(reverse('password_change'), {'new_password1': new_password, 'new_password2': new_password})
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.check_password(new_password))
        self.client.get(reverse('admin_home'))
        self.assert_logged_in_as(self.admin)


class OptionalMFATests(MFATestCase):
    def test_settings_offer_to_enable(self):
        self.login('freiwillig')
        response = self.client.get(reverse('settings'))
        self.assertContains(response, reverse('mfa_enable'))

    def test_enable_leads_to_setup(self):
        self.login('freiwillig')
        response = self.client.post(reverse('mfa_enable'))
        self.assertRedirects(response, reverse('mfa_index'), fetch_redirect_response=False)
        self.assertTrue(mfa.opted_in(self.volunteer))
        self.assertEqual(self.client.get(reverse('mfa_index')).status_code, 200)
        # Still logged in on the rest of the site while the setup is pending.
        self.assertEqual(self.client.get(reverse('settings')).status_code, 200)
        self.assert_logged_in_as(self.volunteer)

    def test_setup_pages_hidden_without_opt_in(self):
        self.login('freiwillig')
        self.assertEqual(self.client.get(reverse('mfa_index')).status_code, 404)

    def test_volunteer_with_totp_needs_code(self):
        mfa.opt_in(self.volunteer)
        secret = add_totp(self.volunteer)
        response = self.login('freiwillig')
        self.assertRedirects(response, reverse('mfa_authenticate'), fetch_redirect_response=False)
        self.assert_logged_out()
        self.enter_code(secret)
        self.assert_logged_in_as(self.volunteer)

    def test_unfinished_opt_in_is_dropped_at_next_login(self):
        mfa.opt_in(self.volunteer)
        self.login('freiwillig')
        self.assert_logged_in_as(self.volunteer)
        self.assertFalse(mfa.opted_in(self.volunteer))
        self.assertRedirects(self.client.get('/'), reverse('fw_home'), fetch_redirect_response=False)

    def test_disable_removes_factors(self):
        mfa.opt_in(self.volunteer)
        secret = add_totp(self.volunteer)
        self.login('freiwillig')
        self.enter_code(secret)
        # Turning it off asks for the password again; the suspended request
        # then runs.
        response = self.client.post(reverse('mfa_disable'))
        self.assertTrue(response['Location'].startswith(reverse('account_reauthenticate')))
        self.assertTrue(Authenticator.objects.filter(user=self.volunteer).exists())
        response = self.client.post(response['Location'], {'password': PASSWORD})
        self.assertRedirects(response, reverse('settings'), fetch_redirect_response=False)
        self.assertFalse(Authenticator.objects.filter(user=self.volunteer).exists())
        self.assertFalse(mfa.opted_in(self.volunteer))
        self.assertTrue(Group.objects.filter(name=mfa.OPT_IN_GROUP).exists())
        # Next login without a second factor.
        self.client.logout()
        self.login('freiwillig')
        self.assert_logged_in_as(self.volunteer)


class RecoveryCodesPageTests(MFATestCase):
    def test_page_has_links_and_home_button(self):
        secret = add_totp(self.admin)
        RecoveryCodes.activate(self.admin)
        self.login('admin')
        self.enter_code(secret)
        # Viewing the codes asks for the password again.
        response = self.client.get(reverse('mfa_view_recovery_codes'))
        self.assertTrue(response['Location'].startswith(reverse('account_reauthenticate')))
        response = self.client.post(response['Location'], {'password': PASSWORD}, follow=True)
        self.assertEqual(response.redirect_chain[-1][0], reverse('mfa_view_recovery_codes'))
        self.assertContains(response, f'<a href="{reverse("mfa_download_recovery_codes")}">', html=False)
        self.assertContains(response, f'<a href="{reverse("mfa_generate_recovery_codes")}">', html=False)
        self.assertContains(response, f'href="{reverse("index_home")}" class="btn btn-primary')
        self.assertContains(response, 'Wiederherstellungs-Codes')

    def test_passkey_list_renders(self):
        # allauth's passkey list needs django.contrib.humanize.
        secret = add_totp(self.admin)
        self.login('admin')
        self.enter_code(secret)
        response = self.client.get(reverse('mfa_list_webauthn'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse('mfa_add_webauthn'))
