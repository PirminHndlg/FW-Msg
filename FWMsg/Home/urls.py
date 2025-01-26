from . import views
from django.urls import path, include

urlpatterns = [
    path('', views.index, name='index_home'),
    path('index', views.index, name='index'),
    path('first_login', views.first_login, name='first_login'),
]
