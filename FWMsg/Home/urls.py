from . import views
from django.urls import path, include

urlpatterns = [
    path('', views.index, name='index'),
    path('index', views.index, name='index'),
]