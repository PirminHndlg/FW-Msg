from . import views
from django.urls import path

urlpatterns = [
    path('', views.home, name='fwhome'),
    path('profil/', views.view_profil, name='profil'),
    path('profil/<int:user_id>', views.view_profil, name='profil'),
    path('profil/remove/<int:profil_id>', views.remove_profil, name='remove_profil'),
    path('ampel/', views.ampel, name='ampel'),
    path('aufgaben/', views.aufgaben, name='aufgaben'),
    path('aufgaben/<int:aufgabe_id>/', views.aufgabe, name='aufgaben_detail'),
    path('logos/<str:image_name>', views.serve_logo, name='serve_image'),
    path('bilder/', views.bilder, name='bilder'),
    path('bilder/<str:image_name>', views.serve_bilder, name='serve_bilder'),
    path('bilder/small/<str:image_name>', views.serve_small_bilder, name='serve_small_bilder'),
    path('bild/', views.bild, name='bild'),
    path('dokumente/', views.dokumente, name='dokumente'),
    path('dokumente/add/', views.add_dokument, name='add_dokument'),
    path('dokument/<str:org_name>/<str:ordner_name>/<str:dokument_name>', views.serve_dokument, name='serve_dokument'),
]