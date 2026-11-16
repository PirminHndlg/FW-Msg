from django.apps import AppConfig


class AdminMFAConfig(AppConfig):
    name = "admin_mfa"
    verbose_name = "Admin 2FA"

    def ready(self) -> None:
        from django.contrib import admin

        from . import audit
        from .admin import protect

        audit.connect()
        # The default admin site; a site with its own AdminSite calls protect().
        protect(admin.site)
