from . import views
from django.urls import path, include

urlpatterns = [
    path('', views.admin_home, name='admin_home'),
    path('organisationen/', views.admin_org, name='admin_org'),
    path('organisationen/<int:org_id>/', views.admin_org, name='admin_org_id'),
]
