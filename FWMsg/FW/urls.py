from . import views
from django.urls import path

urlpatterns = [
    path('', views.home, name='home'),
    path('profil/', views.profil, name='profil'),
    path('ampel/', views.ampel, name='ampel'),
]