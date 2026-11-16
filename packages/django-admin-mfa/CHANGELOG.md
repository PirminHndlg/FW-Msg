# Changelog

## [Unreleased]

## [0.3.1] - 2026-11-15

### Fixed
- First enrolment no longer asks for the password twice. allauth asks for it
  again before any change to the 2FA setup and does not count the login, so
  users were sent to "Enter your password" seconds after logging in, and
  several failed there. A first-enrolment login now counts for
  `ADMIN_MFA_SETUP_GRACE` seconds (default 900), including the recovery codes
  shown after the first factor. Logins that already had a second factor are
  asked as before.
- The password confirmation page carries the username (a hidden
  `autocomplete="username"` field), so password managers fill in the right
  saved login instead of guessing.

### Added
- `login_failed` log lines name the page (`path=`): the login itself or
  allauth's password confirmation.

## [0.3.0] - 2026-11-14

### Added
- The login page offers the browser's saved passkeys in the username field
  (WebAuthn conditional mediation): a user with a passkey signs in without
  clicking "Sign in with a passkey" first. The field has the focus, and
  browsers without a passkey for the site show the plain form.

### Changed
- A passkey added under `/auth/2fa/` is passwordless by default (it signs in
  on its own). Unticking the box still adds it as a second factor only.

## [0.2.0] - 2026-11-13

### Added
- `ADMIN_MFA_APPLIES_TO`: dotted path to a callable `(user) -> bool` naming
  the users the policy is for (default: staff or superuser). For a
  multi-tenant site whose customers have staff accounts of their own.
- `ADMIN_MFA_LOGIN_URL` (default `account_login`): where the admin's login
  and an ended session send the browser, independent of `LOGIN_URL`, which a
  site may keep for its own login page.

### Changed
- The admin login redirect is admin_mfa's own (`admin_mfa.admin.protect`)
  instead of allauth's `secure_admin_login`, which always used `LOGIN_URL`.
- The 2FA setup pages (`/auth/2fa/…`) answer 404 to users the policy does not
  apply to: they log in through the site's own login, which has no second
  factor step, so a factor set up there would protect nothing.

## [0.1.1] - 2026-11-13

### Added
- Admin login through django-allauth: passkeys/WebAuthn, TOTP, recovery
  codes, allauth's login rate limits, "trust this browser" for 30 days.
- Policy for staff and superusers: trusted networks (optionally per user)
  skip the second factor; superusers always need it; first enrolment from
  anywhere or only from trusted networks.
- Middleware: staff sessions need a login record from this flow (no
  password-only logins through other views, no pre-rollout sessions);
  trusted-network sessions end when the client leaves the network; enrolment
  logins reach only the 2FA setup pages; the last second factor cannot be
  removed; unused allauth pages (signup, password reset, e-mail) answer 404.
- `configure()` settings helper, admin-styled templates, `admin_mfa` logger,
  `manage.py admin_mfa_reset`.
