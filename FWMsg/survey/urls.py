from django.urls import path
from . import views

app_name = 'survey'

urlpatterns = [
    # Public survey access
    path('s/<str:survey_key>/', views.survey_detail, name='survey_detail'),
    path('s/<str:survey_key>/thanks/', views.survey_thank_you, name='survey_thank_you'),
    
    # Survey management (requires login)
    path('', views.SurveyListView.as_view(), name='survey_list'),
    path('create/', views.SurveyCreateView.as_view(), name='survey_create'),
    path('<int:pk>/', views.survey_manage, name='survey_manage'),
    path('<int:pk>/edit/', views.SurveyUpdateView.as_view(), name='survey_update'),
    path('<int:pk>/delete/', views.SurveyDeleteView.as_view(), name='survey_delete'),
    path('<int:pk>/results/', views.survey_results, name='survey_results'),
    
    # Question management
    path('<int:survey_pk>/add-question/', views.add_question, name='add_question'),
    path('<int:survey_pk>/question/<int:question_pk>/edit/', views.edit_question, name='edit_question'),
    path('<int:survey_pk>/question/<int:question_pk>/delete/', views.delete_question, name='delete_question'),
    
    # AJAX endpoints
    path('ajax/question-form/', views.get_question_form, name='get_question_form'),
    
    # Admin views
    path('admin/surveys/', views.admin_survey_list, name='admin_survey_list'),
] 