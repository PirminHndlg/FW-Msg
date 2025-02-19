from . import views
from django.urls import path

urlpatterns = [
    path('', views.home, name='team_home'),
    path('contacts/', views.contacts, name='team_contacts'),
    path('ampelmeldung/', views.ampelmeldung, name='team_ampelmeldung'),
    path('einsatzstellen/', views.einsatzstellen, name='team_einsatzstellen'),
    path('laender/', views.laender, name='team_laender'),
]