# django-admin-mfa

Two-factor authentication for the Django admin, shared by the zom/Vector
Django sites. Built on [django-allauth](https://docs.allauth.org/)'s MFA:
passkeys/WebAuthn, TOTP authenticator apps and recovery codes.

## Policy

Applies to active staff users and superusers. Other users are left alone.

| Who / where | Login |
|---|---|
| Staff from a trusted network | password only |
| Staff elsewhere, with a second factor | password + second factor, or a passkey alone; "trust this browser" skips the code for 30 days |
| Staff elsewhere, without one | `ADMIN_MFA_FIRST_ENROLMENT="anywhere"` (default): logged in to the 2FA setup pages only, until a factor is set up. `"trusted"`: refused |
| Superusers | always a second factor (`ADMIN_MFA_SUPERUSER_ALWAYS`, default on) |

### Passkeys

A passkey is the quickest login: it replaces password and code. On the login
page the browser offers the saved passkeys right in the username field
(WebAuthn conditional mediation, `admin_mfa/js/passkey-autofill.js`), so a
user with one picks it there instead of typing; without one the page is the
plain password form. "Sign in with a passkey" stays for passkeys the
autofill cannot list (a security key, a phone nearby).

A passkey added under `/auth/2fa/` is passwordless by default (discoverable,
with PIN or biometrics). Unticking "Passwordless" adds it as a second factor
only — for a security key without a PIN. A passkey added before 0.3.0 was a
second factor only; to sign in with it alone, add it again.

On top of that, `AdminMFAMiddleware`:

- accepts a staff session only if this login flow wrote it — a password-only
  login through another view (a site's own `LoginView`) or a session from
  before the rollout is logged out;
- ends a password-only (trusted-network) session as soon as a request comes
  from elsewhere;
- refuses to remove a staff user's last second factor;
- lets a first enrolment add its factor without asking for the password a
  second time, for `ADMIN_MFA_SETUP_GRACE` seconds after the login (default
  900; `0` restores allauth's prompt);
- answers 404 for the allauth pages these sites do not use (signup, password
  reset by e-mail, e-mail/phone management, login by code).

## Adding it to a site

```toml
# pyproject.toml
dependencies = ["django-admin-mfa @ git+https://git.npnan.com/aha/django-admin-mfa.git@v0.3.0"]
```

```python
# settings.py, after INSTALLED_APPS, MIDDLEWARE, TEMPLATES
from admin_mfa.conf import configure

configure(
    globals(),
    site_name="Passar",              # label in authenticator apps
    trusted_proxy_count=1,           # proxies appending X-Forwarded-For (Caddy: 1)
    trusted_networks=os.environ.get("ADMIN_MFA_TRUSTED_NETWORKS", ""),
)
```

```python
# urls.py
path("auth/", include("admin_mfa.urls")),
```

Then `manage.py migrate` (allauth's tables) and `collectstatic`.

`configure()` adds the apps and middleware, the allauth backend and the
allauth/MFA settings; anything already set in the settings module before the
call is kept. The default `admin.site` is protected automatically; a site
with its own `AdminSite` calls `admin_mfa.admin.protect(site)`.

Requirements: `django.template.context_processors.request` in TEMPLATES, a
shared cache (Redis) when running several workers — allauth's rate limits and
used-TOTP-code markers live in the cache.

Test settings of a site can set `ADMIN_MFA_ENFORCE = False` so that
`Client.force_login()` keeps working there.

### Narrowing the policy (multi-tenant sites)

`ADMIN_MFA_APPLIES_TO = "myproject.mfa.operators_only"` names a callable
`(user) -> bool`; only those users get the policy. Everyone else keeps the
site's own login and cannot reach the 2FA setup pages. Keep `LOGIN_URL` on the
site's own login page if it has one: the admin login and ended sessions go to
`ADMIN_MFA_LOGIN_URL` (default `account_login`) regardless. A site's own login
view should then send policy users to the 2FA login instead of logging them in
(`admin_mfa.policy.applies_to(user)`), or the middleware ends their session on
the next request.

### Client IP

Trusted networks are matched against allauth's client IP:
`ALLAUTH_TRUSTED_PROXY_COUNT` entries from the right of `X-Forwarded-For`,
else `REMOTE_ADDR`. That is only sound if the app's port accepts connections
from the proxy alone.

### Trusted networks

```
ADMIN_MFA_TRUSTED_NETWORKS=192.0.2.0/24; 198.51.100.7/32=alice
```

`cidr` trusts every staff user there, `cidr=user1,user2` only those
usernames. Entries are separated by `;` or newlines. A host address with a
prefix (`192.0.2.1/24`) is rejected as a typo.

## Operations

- **Lost device:** `manage.py admin_mfa_reset <username>` removes the user's
  passkeys, TOTP and recovery codes; the next login sets up a new one
  (`ADMIN_MFA_FIRST_ENROLMENT`). Recovery codes are only the user's own way
  past a lost device; an admin needs none of them. In the admin, *MFA →
  Authenticators* (filter by user) deletes them too, without the
  `authenticators_reset_by_command` log line. Until the user has set up a new
  factor, whoever knows the password can set one up, so after a lost or
  stolen device set a new password as well and hand it over in person.
- **Lost password:** no reset by e-mail; an admin sets a new one in the
  admin (the user's page → the password form). The second factor stays
  as it was.
- **Managing factors:** `/auth/2fa/` (linked in the header of the login pages).
- **Log:** logger `admin_mfa` — `login` (mode, matched rule), `login_failed` (path),
  `login_refused`, `session_ended` (reason), `enrolled`, `authenticator_*`,
  each with user, IP and user agent.

## Upgrading allauth

`admin_mfa.stages` subclasses allauth's MFA login stage. The dependency is
capped below the next allauth major; `tests/test_allauth_contract.py` and
`tests/test_flow.py` are what to run before raising it.

## Development

```
uv sync
uv run pytest
```
