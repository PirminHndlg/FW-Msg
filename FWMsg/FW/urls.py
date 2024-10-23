from . import views
from django.urls import path

urlpatterns = [
    path('', views.home, name='fwhome'),
    path('profil/', views.profil, name='profil'),
    path('ampel/', views.ampel, name='ampel'),
    path('aufgaben/', views.aufgaben, name='aufgaben'),
]