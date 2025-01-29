from . import views
from django.urls import path

urlpatterns = [
    path('', views.home, name='org_home'),

    path('add/<str:model_name>/', views.add_object, name='add_object'),
    path('add/<str:model_name>/excel/', views.add_objects_from_excel, name='add_objects_from_excel'),
    path('edit/<str:model_name>/<int:id>', views.edit_object, name='edit_object'),
    path('list/<str:model_name>/', views.list_object, name='list_object'),
    path('list/<str:model_name>/<int:highlight_id>', views.list_object, name='list_object_highlight'),
    path('update/<str:model_name>/', views.update_object, name='update_object'),
    path('delete/<str:model_name>/<int:id>', views.delete_object, name='delete_object'),
    path('list-ampel/', views.list_ampel, name='list_ampel'),
    path('list-aufgaben/', views.list_aufgaben, name='list_aufgaben'),
    path('list-aufgaben-table/', views.list_aufgaben_table, name='list_aufgaben_table'),
    path('aufgaben-assign/', views.aufgaben_assign, name='aufgaben_assign'),
    path('download-aufgabe/<int:id>', views.download_aufgabe, name='download_aufgabe'),
    path('download-bild/<int:id>', views.download_bild_as_zip, name='download_bild_as_zip'),
    path('list-bilder/', views.list_bilder, name='list_bilder'),
]
