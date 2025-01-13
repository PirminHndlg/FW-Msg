from django.contrib import admin
from django.urls import path, include
from django.conf.urls.i18n import i18n_patterns
from django.utils.translation import gettext_lazy as _

# URLs that don't need language prefix
urlpatterns = [
    path('i18n/', include('django.conf.urls.i18n')),
]

# URLs that should have language prefix
urlpatterns += i18n_patterns(
    path('admin/', admin.site.urls),
    path('', include('FW.urls')),
    path('org/', include('ORG.urls')),
    prefix_default_language=True  # This will add /de/ prefix for German URLs
) 