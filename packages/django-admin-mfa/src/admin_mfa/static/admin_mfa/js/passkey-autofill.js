// Offer the browser's saved passkeys on the login page without a click on
// "Sign in with a passkey": a WebAuthn request with conditional mediation
// lists them in the username field's autofill (autocomplete="username
// webauthn", see admin_mfa.forms.LoginForm). The browser shows nothing if
// there is no passkey for this site, so users without one see the plain form.
//
// Uses allauth's passkey login form (#mfa_login) and webauthn-json, both
// included by mfa/webauthn/snippets/login_script.html before this script.
(function () {
  'use strict'

  async function start () {
    const PKC = window.PublicKeyCredential
    if (!PKC || typeof PKC.isConditionalMediationAvailable !== 'function') return
    if (!(await PKC.isConditionalMediationAvailable())) return

    const form = document.getElementById('mfa_login')
    const credentialInput = document.getElementById('mfa_credential')
    const button = document.getElementById('passkey_login')
    if (!form || !credentialInput || !window.webauthnJSON) return

    // A browser runs one WebAuthn request at a time: the button's own
    // (allauth's, modal) request must not find this one still pending.
    // Capture, so this runs before allauth's click handler.
    const controller = new AbortController()
    if (button) {
      button.addEventListener('click', function () { controller.abort() }, { capture: true })
    }

    try {
      const response = await fetch(form.action, {
        method: 'GET',
        headers: { Accept: 'application/json' },
        signal: controller.signal
      })
      if (!response.ok) return
      const options = (await response.json()).request_options
      // Autofill stays offered as long as the page is open.
      delete options.publicKey.timeout
      const credential = await window.webauthnJSON.get({
        ...options,
        mediation: 'conditional',
        signal: controller.signal
      })
      credentialInput.value = JSON.stringify(credential)
      form.submit()
    } catch (e) {
      // AbortError: the button took over. NotAllowedError: the page is being
      // left (password submitted) or the user dismissed the prompt.
      if (e.name !== 'AbortError' && e.name !== 'NotAllowedError') console.warn('passkey autofill:', e)
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start)
  } else {
    start()
  }
})()
