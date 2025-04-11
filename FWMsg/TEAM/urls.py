from . import views
from django.urls import path

urlpatterns = [
    path('', views.home, name='team_home'),
    path('contacts/', views.contacts, name='team_contacts'),
    path('ampelmeldung/', views.ampelmeldung, name='team_ampelmeldung'),
    path('einsatzstellen/', views.einsatzstellen, name='einsatzstellen'),
    path('einsatzstellen/save/<int:stelle_id>/', views.save_einsatzstelle_info, name='save_einsatzstelle_info'),
    path('laender/', views.laender, name='laender'),
    path('laender/save/<int:land_id>/', views.save_land_info, name='save_land_info'),
]