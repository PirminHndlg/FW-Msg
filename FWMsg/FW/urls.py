from . import views
from django.urls import path

urlpatterns = [
    path('', views.home, name='fwhome'),
    path('profil/', views.profil, name='profil'),
    path('ampel/', views.ampel, name='ampel'),
    path('aufgaben/', views.aufgaben, name='aufgaben'),
    path('aufgaben/<int:aufgabe_id>/', views.aufgabe, name='aufgaben_detail'),
    path('logos/<str:image_name>', views.serve_logo, name='serve_image'),
    path('bilder/', views.bilder, name='bilder'),
    path('bilder/<str:image_name>', views.serve_bilder, name='serve_bilder'),
    path('bild/', views.bild, name='bild'),
]