from . import views
from django.urls import path, include

urlpatterns = [
    path('', views.home, name='fw_home'),
    path('profil/remove/<int:profil_id>', views.remove_profil_attribut, name='remove_profil_attribut'),
    path('ampel/', views.ampel, name='ampel'),
    path('aufgaben/', views.aufgaben, name='aufgaben'),
    path('aufgaben/<int:aufgabe_id>/', views.aufgabe, name='aufgaben_detail'),

    path('i18n/', include('django.conf.urls.i18n')),  # Language switcher URL
]