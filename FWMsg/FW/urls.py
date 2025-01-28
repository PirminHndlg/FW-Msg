from . import views
from django.urls import path, include

urlpatterns = [
    path('', views.home, name='fw_home'),
    path('ampel/', views.ampel, name='ampel'),
    path('aufgaben/', views.aufgaben, name='aufgaben'),
    path('aufgaben/<int:aufgabe_id>/', views.aufgabe, name='aufgaben_detail'),

    path('i18n/', include('django.conf.urls.i18n')),  # Language switcher URL
]