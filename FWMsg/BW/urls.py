from . import views
from django.urls import path, include

urlpatterns = [
    path('', views.home, name='bw_home'),
    path('neue_bewerbung/<int:org_id>/', views.create_account, name='bw_create_account'),
    path('bewerbung_erstellt/', views.account_created, name='account_created'),
    path('bewerbung_verifiziert/<str:token>/', views.verify_account, name='verify_account'),
    
    path('questions/', views.bw_application_questions_list, name='bw_application_questions_list'),
    path('questions/<int:question_id>/', views.bw_application_answer, name='bw_application_answer'),
    path('answers/', views.bw_application_answers_list, name='bw_application_answers_list'),
    path('complete/', views.bw_application_complete, name='bw_application_complete'),
    path('files/', views.bw_application_files_list, name='bw_application_files_list'),
    path('files/<int:file_question_id>/', views.bw_application_file_answer, name='bw_application_file_answer'),
    path('files/download/<int:file_answer_id>/', views.bw_application_file_answer_download, name='bw_application_file_answer_download'),
    path('files/delete/<int:file_answer_id>/', views.bw_application_file_answer_delete, name='bw_application_file_answer_delete'),
]