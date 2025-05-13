from . import views
from django.urls import path

urlpatterns = [
    path('', views.home, name='team_home'),
    path('contacts/', views.contacts, name='team_contacts'),
    path('ampelmeldung/', views.ampelmeldung, name='team_ampelmeldung'),
    path('einsatzstellen/', views.einsatzstellen, name='team_einsatzstellen'),
    path('einsatzstellen/save/<int:stelle_id>/', views.save_einsatzstelle_info, name='team_save_einsatzstelle_info'),
    path('laender/', views.laender, name='team_laender'),
    path('laender/save/<int:land_id>/', views.save_land_info, name='team_save_land_info'),
]