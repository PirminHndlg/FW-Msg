from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home-seminar'),
    path('start/', views.start, name='start'),
    path('refresh/', views.refresh, name='refresh'),
    path('evaluate/', views.evaluate, name='evaluate'),
    path('evaluate-post/', views.evaluate_post, name='evaluate-post'),
    path('einheit/', views.einheit, name='einheit'),
    path('choose/', views.choose, name='choose'),
    path('land/', views.land, name='land'),
    path('verschwiegenheit/', views.verschwiegenheit, name='verschwiegenheit'),

    path('auswertung/', views.evaluate_all, name='evaluate_all'),
    path('auswertung/geeignet/', views.insert_geeingnet, name='insert_geeignet'),
    # path('user/', views.user_overview, name='user'),
    path('zuteilung/', views.assign, name='assign'),
    path('auto-zuteilung/', views.auto_assign, name='auto_assign'),
    path('sum/', views.summerizeComments, name='summary'),
]