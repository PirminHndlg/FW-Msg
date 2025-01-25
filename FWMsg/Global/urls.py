from . import views
from django.urls import path 

urlpatterns = [
    path('logos/<str:image_name>', views.serve_logo, name='serve_image'),
    path('bilder/', views.bilder, name='bilder'),
    path('bilder/<int:image_id>', views.serve_bilder, name='serve_bilder'),
    path('bilder/small/<int:image_id>', views.serve_small_bilder, name='serve_small_bilder'),
    path('bild/', views.bild, name='bild'),
    path('bild/remove/', views.remove_bild, name='remove_bild'),
    path('bild/remove/all/', views.remove_bild_all, name='remove_bild_all'),
    path('dokumente/', views.dokumente, name='dokumente'),
    path('dokumente/add/', views.add_dokument, name='add_dokument'),
    path('dokumente/remove/', views.remove_dokument, name='remove_dokument'),
    path('dokument/<int:dokument_id>/', views.serve_dokument, name='serve_dokument'),
    path('dokumente/remove_ordner/', views.remove_ordner, name='remove_ordner'),
    path('dokumente/add_ordner/', views.add_ordner, name='add_ordner'),
    path('profil_picture/', views.update_profil_picture, name='update_profil_picture'),
    path('profil_picture/<int:user_id>', views.serve_profil_picture, name='serve_profil_picture'),

    path('profil/', views.view_profil, name='profil'),
    path('profil/<int:user_id>', views.view_profil, name='profil'),

    path('datenschutz/', views.datenschutz, name='datenschutz'),

    path('send_aufgaben_email/', views.send_aufgaben_email, name='send_aufgaben_email'),
]