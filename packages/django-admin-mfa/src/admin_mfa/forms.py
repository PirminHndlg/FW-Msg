"""allauth's forms with admin_mfa's defaults (wired in by ``configure()``)."""

from __future__ import annotations

from allauth.account.forms import LoginForm as AllauthLoginForm
from allauth.mfa.webauthn.forms import AddWebAuthnForm as AllauthAddWebAuthnForm


class LoginForm(AllauthLoginForm):
    """The login field also offers the browser's saved passkeys.

    ``webauthn`` in ``autocomplete`` is what lets the browser list passkeys in
    the field's autofill (conditional mediation, started by
    ``admin_mfa/js/passkey-autofill.js``); the field has the focus so the list
    is one tap away.
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        attrs = self.fields["login"].widget.attrs
        attrs["autocomplete"] = "username webauthn"
        attrs["autofocus"] = True


class AddWebAuthnForm(AllauthAddWebAuthnForm):
    """A new passkey signs in on its own unless the user unticks it.

    Passwordless asks the authenticator for a discoverable credential and user
    verification (PIN or biometrics), which is what a passkey is; a security
    key without a PIN can still be added as a second factor by unticking.
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        if "passwordless" in self.fields:
            self.fields["passwordless"].initial = True
