from . import views
from django.urls import path

urlpatterns = [
    path('', views.home, name='org_home'),

    path('add/<str:model_name>/', views.add_object, name='add_object'),
    path('add/<str:model_name>/excel/', views.add_objects_from_excel, name='add_objects_from_excel'),
    path('edit/<str:model_name>/<int:id>', views.edit_object, name='edit_object'),
    path('list/<str:model_name>/', views.list_object, name='list_object'),
    path('list/<str:model_name>/<int:highlight_id>', views.list_object, name='list_object_highlight'),
    path('delete/<str:model_name>/<int:id>', views.delete_object, name='delete_object'),
    
    path('delete-zwischenschritt/', views.delete_zwischenschritt, name='delete_zwischenschritt'),
    path('list-ampel/', views.list_ampel, name='list_ampel'),
    path('list-aufgaben-table/', views.list_aufgaben_table, name='list_aufgaben_table'),
    path('list-aufgaben-table/<int:scroll_to>', views.list_aufgaben_table, name='list_aufgaben_table_scroll'),
    path('get-aufgaben-zwischenschritte/', views.get_aufgaben_zwischenschritte, name='get_aufgaben_zwischenschritte'),
    path('toggle-zwischenschritt-status/', views.toggle_zwischenschritt_status, name='toggle_zwischenschritt_status'),
    path('get-zwischenschritt-form/', views.get_zwischenschritt_form, name='get_zwischenschritt_form'),
    
    path('bewerbung-overview/', views.application_overview, name='application_overview'),
    path('bewerbung-liste/', views.application_list, name='application_list'),
    path('bewerbung-detail/<int:id>', views.application_detail, name='application_detail'),
    path('bewerbung-answer-download/<int:bewerber_id>', views.application_answer_download, name='application_answer_download'),
    path('bewerbung-answer-download-fields/<int:bewerber_id>', views.application_answer_download_fields, name='application_answer_download_fields'),
    
    path('download-aufgabe/<int:id>', views.download_aufgabe, name='download_aufgabe'),
    path('download-bild/<int:id>', views.download_bild_as_zip, name='download_bild_as_zip'),
    path('statistik/', views.statistik, name='statistik'),

    path('nginx-statistic/', views.nginx_statistic, name='nginx_statistic'),

    path('send-registration-mail/', views.send_registration_mail, name='send_registration_mail'),
    path('get-cascade-info/', views.get_cascade_info, name='get_cascade_info'),
    path('create-sticky-note/', views.create_sticky_note, name='create_sticky_note'),
    path('delete-sticky-note/', views.delete_sticky_note, name='delete_sticky_note'),
]
