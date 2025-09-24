from . import views
from django.urls import path 
from . import views_push

urlpatterns = [
    path('logos/<int:org_id>', views.serve_logo, name='serve_image'),
    path('bilder/', views.bilder, name='bilder'),
    path('serve_bilder/<int:image_id>', views.serve_bilder, name='serve_bilder'),
    path('serve_bilder/', views.serve_bilder, name='serve_bilder'),
    path('serve_small_bilder/<int:image_id>', views.serve_small_bilder, name='serve_small_bilder'),
    path('serve_small_bilder/', views.serve_small_bilder, name='serve_small_bilder'),
    path('bilder/<int:image_id>/', views.image_detail, name='image_detail'),
    path('bilder/add', views.bild, name='bild'),
    path('bilder/remove/', views.remove_bild, name='remove_bild'),
    path('bilder/remove/all/', views.remove_bild_all, name='remove_bild_all'),
    
    # Bilder Comments and Reactions
    path('bilder/<int:bild_id>/comment/add/', views.add_comment_to_bild, name='add_comment_to_bild'),
    path('bilder/comment/<int:comment_id>/remove/', views.remove_comment_from_bild, name='remove_comment_from_bild'),
    path('bilder/<int:bild_id>/reaction/<str:emoji>/', views.toggle_reaction_to_bild, name='toggle_reaction_to_bild'),
    path('bilder/<int:bild_id>/reactions/', views.get_bild_reactions, name='get_bild_reactions'),
    path('bilder/edit/<int:bild_id>/', views.edit_bild, name='edit_bild'),

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
    path('aufgaben/attachment/<int:aufgabe_id>/', views.download_aufgabe_attachment, name='download_aufgabe_attachment'),
    path('notfallkontakte/', views.notfallkontakte, name='notfallkontakte'),

    path('profil/', views.view_profil, name='profil'),
    path('profil/<int:user_id>', views.view_profil, name='profil'),
    path('profil/remove/<int:profil_id>', views.remove_profil_attribut, name='remove_profil_attribut'),
    path('unsubscribe_mail_notifications/<int:user_id>/<str:auth_key>', views.unsubscribe_mail_notifications, name='unsubscribe_mail_notifications'),

    path('feedback/', views.feedback, name='feedback'),
    path('settings/', views.settings_view, name='settings'),
    path('settings/delete_account/', views.delete_account, name='delete_account'),
    path('settings/export_data/', views.export_data, name='export_data'),

    path('kalender/', views.kalender, name='kalender'),
    path('kalender/<int:kalender_id>/', views.kalender_event, name='kalender_event'),
    path('calendar_events/', views.get_calendar_events, name='get_calendar_events'),
    path('kalender_abbonement/<str:token>/', views.kalender_abbonement, name='kalender_abbonement'),

    path('datenschutz/', views.datenschutz, name='datenschutz'),
    
    # Einsatzstellen Notizen
    path('einsatzstellen_notiz/', views.einsatzstellen_notiz, name='einsatzstellen_notiz'),
    path('einsatzstellen_notiz/<int:es_id>/', views.einsatzstellen_notiz, name='einsatzstellen_notiz'),
    # path('test_email/', views.test_email, name='test_email'),
]

# Add these new URL patterns
urlpatterns += [
    path('push/', views_push.push_settings, name='push_settings'),
    path('push/save-subscription/', views_push.save_subscription, name='save_subscription'),
    path('push/remove-subscription/<int:subscription_id>/', views_push.remove_subscription, name='remove_subscription'),
    path('push/vapid-public-key/', views_push.vapid_public_key, name='vapid_public_key'),
    path('push/test-notification/', views_push.test_notification, name='test_notification'),
    path('service-worker.js', views_push.service_worker, name='service_worker'),
]