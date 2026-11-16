"""2FA for the Django admin on top of django-allauth's MFA.

See README.md. Wiring a site: ``admin_mfa.conf.configure(globals(), ...)`` in
settings, ``path("auth/", include("admin_mfa.urls"))`` in the root URLconf.
"""

__version__ = "0.3.1"
