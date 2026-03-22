from django.urls import path
from . import views

urlpatterns = [
    path('', views.chat_list, name='chat_list'),
    path('c/<str:identifier>/', views.chat_direct, name='chat_direct'),
    path('chat/<str:identifier>/send/', views.send_message_direct, name='send_message_direct'),
    path('g/<str:identifier>/', views.chat_group, name='chat_group'),
    path('group/<str:identifier>/send/', views.send_message_group, name='send_message_group'),
    path('group/<str:identifier>/manage/', views.manage_chat_group, name='manage_chat_group'),
    path('group/<str:identifier>/delete/', views.delete_chat_group, name='delete_chat_group'),
    path('group/<str:identifier>/leave/', views.leave_chat_group, name='leave_chat_group'),
    path('create-group/', views.create_chat_group, name='create_chat_group'),
    path('create-direct/', views.create_chat_direct, name='create_chat_direct'),
    # AJAX endpoints
    path('ajax/poll/', views.ajax_chat_poll, name='ajax_chat_poll'),
    path('ajax/list/', views.ajax_chat_list_updates, name='ajax_chat_list_updates'),
    path('ajax/updates/<str:chat_type>/<str:chat_id>/', views.ajax_chat_updates, name='ajax_chat_updates'),
]
