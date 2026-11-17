from django.urls import include, path

# Mounted by the site, e.g. path("auth/", include("admin_mfa.urls")).
# Everything allauth offers beyond login, logout, reauthentication and the
# 2FA pages answers 404 (AdminMFAMiddleware.ALLOWED_ALLAUTH_URLS).
urlpatterns = [path("", include("allauth.urls"))]
