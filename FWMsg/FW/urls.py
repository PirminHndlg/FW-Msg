from . import views
from django.urls import path

urlpatterns = [
    path('', views.home, name='fw_home'),
    path('laenderinfo/', views.laenderinfo, name='laenderinfo'),
]