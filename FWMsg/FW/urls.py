from . import views
from django.urls import path, include

urlpatterns = [
    path('', views.home, name='fw_home'),
    path('laenderinfo/', views.laenderinfo, name='laenderinfo'),
    path('i18n/', include('django.conf.urls.i18n')),  # Language switcher URL
]