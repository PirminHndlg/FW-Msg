from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("auth/", include("admin_mfa.urls")),
    # Stands for a site's own password-only login (zomarchive's tenant login).
    path("plain-login/", auth_views.LoginView.as_view(template_name="plain_login.html"), name="plain_login"),
]
