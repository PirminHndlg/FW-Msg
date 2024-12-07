from . import views
from django.urls import path

urlpatterns = [
    path('', views.home, name='org_home'),

    path('add/<str:model_name>/', views.add_object, name='add_object'),
    path('edit/<str:model_name>/<int:id>', views.edit_object, name='edit_object'),
    path('list/<str:model_name>/', views.list_object, name='list_object'),
    path('update/<str:model_name>/', views.update_object, name='update_object'),
    path('delete/<str:model_name>/<int:id>', views.delete_object, name='delete_object'),
]