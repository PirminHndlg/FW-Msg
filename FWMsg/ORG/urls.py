from . import views
from django.urls import path

urlpatterns = [
    path('', views.home, name='org_home'),

    path('add/<str:model_name>/', views.add_object, name='add_object'),
    path('edit/<str:model_name>/<int:id>', views.edit_object, name='edit_object'),
    path('list/<str:model_name>/', views.list_object, name='list_object'),
    path('update/<str:model_name>/', views.update_object, name='update_object'),
    path('delete/<str:model_name>/<int:id>', views.delete_object, name='delete_object'),
    path('list-ampel/', views.list_ampel, name='list_ampel'),
    path('list-ampel/<int:fid>', views.list_ampel_history, name='list_ampel_history'),
    path('list-aufgaben/', views.list_aufgaben, name='list_aufgaben'),
    path('aufgaben-assign/', views.aufgaben_assign, name='aufgaben_assign'),
    path('aufgaben-assign/<str:jahrgang>', views.aufgaben_assign, name='aufgaben_assign'),
    path('download-bild/<int:id>', views.download_bild_as_zip, name='download_bild_as_zip'),
    path('list-bilder/', views.list_bilder, name='list_bilder'),
]
