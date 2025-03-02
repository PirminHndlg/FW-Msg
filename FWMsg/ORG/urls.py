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
    path('delete-zwischenschritt/', views.delete_zwischenschritt, name='delete_zwischenschritt'),
    path('list-ampel/', views.list_ampel, name='list_ampel'),
    path('list-aufgaben/', views.list_aufgaben, name='list_aufgaben'),
    path('list-aufgaben-table/', views.list_aufgaben_table, name='list_aufgaben_table'),
    path('list-aufgaben-table/<int:scroll_to>', views.list_aufgaben_table, name='list_aufgaben_table_scroll'),
    path('get-aufgaben-zwischenschritte/', views.get_aufgaben_zwischenschritte, name='get_aufgaben_zwischenschritte'),
    path('toggle-zwischenschritt-status/', views.toggle_zwischenschritt_status, name='toggle_zwischenschritt_status'),
    path('get-zwischenschritt-form/', views.get_zwischenschritt_form, name='get_zwischenschritt_form'),
    path('aufgaben-assign/', views.aufgaben_assign, name='aufgaben_assign'),
    path('download-aufgabe/<int:id>', views.download_aufgabe, name='download_aufgabe'),
    path('download-bild/<int:id>', views.download_bild_as_zip, name='download_bild_as_zip'),
    path('list-bilder/', views.list_bilder, name='list_bilder'),
    path('statistik/', views.statistik, name='statistik'),

    path('nginx-statistic/', views.nginx_statistic, name='nginx_statistic'),
]
