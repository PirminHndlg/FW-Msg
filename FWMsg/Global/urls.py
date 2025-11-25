from . import views
from django.urls import path 
from . import views_push
from . import views_change_requests

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
    path('bilder/download/<int:id>', views.download_bild_as_zip, name='download_bild_as_zip'),
    

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
    path('dokumente/get_public_link/<int:ordner_id>/', views.get_public_link_ordner, name='get_public_link_ordner'),
    
    path('profil_picture/', views.update_profil_picture, name='update_profil_picture'),
    path('profil_picture/<str:user_identifier>/', views.serve_profil_picture, name='serve_profil_picture'),

    path('ampel/', views.ampel, name='ampel'),
    path('list-ampel/', views.list_ampel, name='list_ampel'),
    
    path('aufgaben/', views.aufgaben, name='aufgaben'),
    path('aufgaben/<int:aufgabe_id>/', views.aufgabe, name='aufgaben_detail'),
    path('aufgaben/attachment/<int:aufgabe_id>/', views.download_aufgabe_attachment, name='download_aufgabe_attachment'),
    path('notfallkontakte/', views.notfallkontakte, name='notfallkontakte'),

    path('profil/', views.view_profil, name='profil'),
    path('profil/<str:user_identifier>', views.view_profil, name='profil'),
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
    
    path('bewerber/', views.list_bewerber, name='list_bewerber'),
    path('bewerber/<int:bewerber_id>/', views.bewerber_detail, name='bewerber_detail'),
    path('bewerber/files/download/<int:file_answer_id>/', views.bw_application_file_answer_download, name='bw_application_file_answer_download'),
    path('bewerber/kommentar/<int:bewerber_id>/', views.bewerber_kommentar, name='bewerber_kommentar'),
    
    # API endpoints for bewerber comments
    path('api/bewerber/<int:bewerber_id>/kommentare/', views.api_bewerber_kommentare, name='api_bewerber_kommentare'),
    path('api/bewerber/<int:bewerber_id>/kommentare/<int:kommentar_id>/', views.api_bewerber_kommentare, name='api_bewerber_kommentar_detail'),
    
    # Country and Placement Location Information (for Team and Ehemalige members)
    path('laender/', views.laender_info, name='laender_info'),
    path('einsatzstellen/', views.einsatzstellen_info, name='einsatzstellen_info'),
    
    # Change Request Actions
    path('einsatzstellen/save/<int:stelle_id>/', views_change_requests.save_einsatzstelle_info, name='save_einsatzstelle_info'),
    path('laender/save/<int:land_id>/', views_change_requests.save_land_info, name='save_land_info'),
    
    path('karte/', views.karte, name='karte'),
    path('karte/delete/', views.delete_karte, name='delete_karte'),
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