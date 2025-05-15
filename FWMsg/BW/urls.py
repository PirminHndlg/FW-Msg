from . import views
from django.urls import path, include

urlpatterns = [
    path('', views.home, name='bw_home'),
    path('create_account/<int:org_id>/', views.create_account, name='bw_create_account'),
    path('questions/', views.bw_application_questions_list, name='bw_application_questions_list'),
    path('questions/<int:question_id>/', views.bw_application_answer, name='bw_application_answer'),
    path('answers/', views.bw_application_answers_list, name='bw_application_answers_list'),
    path('complete/', views.bw_application_complete, name='bw_application_complete'),
]