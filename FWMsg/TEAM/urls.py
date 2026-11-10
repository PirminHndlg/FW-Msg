from . import views
from django.urls import path
from django.shortcuts import redirect

urlpatterns = [
    path('', views.home, name='team_home'),
    path('contacts/', views.contacts, name='team_contacts'),
    path('aufgabenuebersicht/', views.aufgabenuebersicht, name='team_aufgabenuebersicht'),
]