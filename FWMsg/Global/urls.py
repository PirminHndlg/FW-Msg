from . import views
from django.urls import path 

urlpatterns = [
    path('logos/<int:org_id>', views.serve_logo, name='serve_image'),
    path('bilder/', views.bilder, name='bilder'),
    path('bilder/<int:image_id>', views.serve_bilder, name='serve_bilder'),
    path('bilder/small/<int:image_id>', views.serve_small_bilder, name='serve_small_bilder'),
    path('bild/', views.bild, name='bild'),
    path('bild/remove/', views.remove_bild, name='remove_bild'),
    path('bild/remove/all/', views.remove_bild_all, name='remove_bild_all'),

    path('posts/', views.posts_overview, name='posts_overview'),
    path('posts/add/', views.post_add, name='post_add'),
    path('posts/<int:post_id>/', views.post_detail, name='post_detail'),
    path('posts/edit/<int:post_id>/', views.post_edit, name='post_edit'),
    path('posts/vote/<int:post_id>/', views.post_vote, name='post_vote'),
    path('posts/delete/<int:post_id>/', views.post_delete, name='post_delete'),

    path('dokumente/', views.dokumente, name='dokumente'),
    path('dokumente/<int:ordner_id>/', views.dokumente, name='dokumente'),
    path('dokumente/add/', views.add_dokument, name='add_dokument'),
    path('dokumente/remove/', views.remove_dokument, name='remove_dokument'),
    path('dokument/<int:dokument_id>/', views.serve_dokument, name='serve_dokument'),
    path('dokumente/remove_ordner/', views.remove_ordner, name='remove_ordner'),
    path('dokumente/add_ordner/', views.add_ordner, name='add_ordner'),
    path('profil_picture/', views.update_profil_picture, name='update_profil_picture'),
    path('profil_picture/<int:user_id>', views.serve_profil_picture, name='serve_profil_picture'),

    path('ampel/', views.ampel, name='ampel'),
    path('aufgaben/', views.aufgaben, name='aufgaben'),
    path('aufgaben/<int:aufgabe_id>/', views.aufgabe, name='aufgaben_detail'),
    path('notfallkontakte/', views.notfallkontakte, name='notfallkontakte'),

    path('profil/', views.view_profil, name='profil'),
    path('profil/<int:user_id>', views.view_profil, name='profil'),
    path('profil/remove/<int:profil_id>', views.remove_profil_attribut, name='remove_profil_attribut'),
    path('unsubscribe_mail_notifications/<int:user_id>/<str:auth_key>', views.unsubscribe_mail_notifications, name='unsubscribe_mail_notifications'),

    path('feedback/', views.feedback, name='feedback'),

    path('kalender/', views.kalender, name='kalender'),
    path('calendar_events/', views.get_calendar_events, name='get_calendar_events'),
    
    path('datenschutz/', views.datenschutz, name='datenschutz'),

    # path('test_email/', views.test_email, name='test_email'),
]