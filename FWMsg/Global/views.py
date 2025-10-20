"""
Global views for the FWMsg application.

This module contains view functions for handling general functionality like:
- Image and document serving
- Profile management
- Gallery and image handling
- Calendar functionality
- Organization-specific context handling

The views are organized into logical sections:
1. Context and utility functions
2. File serving views
3. Gallery and image management
4. Document management
5. Profile management
6. Calendar and event handling
"""

# Standard library imports
from datetime import datetime, timedelta, timezone as dt_timezone
import io
import json
import mimetypes
import os
import zipfile
import hashlib
import logging
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.utils.html import strip_tags
import re
from django.core.serializers import serialize
from django.db.models import Model
from django.apps import apps

# Django imports
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.contrib.auth.models import User
from django.contrib.auth import login
from django.conf import settings
from django.http import (
    FileResponse,
    HttpResponseForbidden,
    HttpResponseRedirect, 
    HttpResponse, 
    Http404, 
    HttpResponseNotAllowed, 
    HttpResponseNotFound,
    JsonResponse
)
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from uuid import UUID
import uuid

from BW.models import ApplicationAnswer, ApplicationAnswerFile, Bewerber
from Global.send_email import send_email_with_archive
from Global.tasks import send_image_uploaded_email_task
from TEAM.models import Team
from django.core.mail import send_mail

from django.core.files.base import ContentFile
from django.core import signing
from icalendar import Calendar, Event
from django.utils import timezone

# Local application imports
from FW.forms import BilderForm, BilderGalleryForm, ProfilUserForm
from .models import (
    Ampel2, 
    Aufgabe2,
    BewerberKommentar,
    Bilder2, 
    BilderGallery2,
    Einsatzstelle2,
    EinsatzstelleNotiz, 
    ProfilUser2,
    UserAttribute, 
    UserAufgaben,
    UserAufgabenZwischenschritte,
    KalenderEvent,
    CustomUser,
    Dokument2,
    Ordner2,
    PersonCluster,
    Notfallkontakt2,
    DokumentColor2,
    Post2,
    PostSurveyAnswer,
    PushSubscription,
    StickyNote,
    ChangeRequest
)
from ORG.models import Organisation
from FW.models import Freiwilliger
from ORG.views import base_template as org_base_template
from TEAM.views import base_template as team_base_template
from FW.views import base_template as fw_base_template
from BW.views import base_template as bw_base_template
from Ehemalige.views import base_template as ehemalige_base_template
from FWMsg.celery import send_email_aufgaben_daily
from FWMsg.decorators import required_person_cluster, required_role
from .forms import BewerberKommentarForm, EinsatzstelleNotizForm, FeedbackForm, AddPostForm, AddAmpelmeldungForm
from ORG.forms import AddNotfallkontaktForm
from .export_utils import export_user_data_securely


# Utility Functions
def get_mimetype(doc_path):
    """
    Determine the MIME type of a file.
    
    Args:
        doc_path (str): Path to the document
        
    Returns:
        str: The MIME type of the file, or None if it cannot be determined
    """
    mime_type, _ = mimetypes.guess_type(doc_path)
    return mime_type

def get_bild(image_path, image_name):
    """
    Serve an image file with proper headers.
    
    Args:
        image_path (str): Path to the image file
        image_name (str): Name of the image for the response header
        
    Returns:
        HttpResponse: Response containing the image file
        
    Raises:
        Http404: If the image file does not exist
    """
    if not os.path.exists(image_path):
        raise Http404("Image does not exist")

    with open(image_path, 'rb') as img_file:
        content_type = 'image/jpeg'  # Default content type
        response = HttpResponse(img_file.read(), content_type=content_type)
        response['Content-Disposition'] = f'inline; filename="{image_name}"'
        return response

def get_bilder(org, filter_user=None, filter_person_cluster=None, limit=None):
    """
    Retrieve gallery images, optionally filtered by user.
    
    Args:
        org: The organization object
        filter_user (User, optional): User to filter images by. Defaults to None.
        filter_person_cluster: Person cluster to filter by. Defaults to None.
        limit (int, optional): Limit number of results. Defaults to None.
        
    Returns:
        list: List of dictionaries containing gallery images and their metadata
    """

    if filter_person_cluster:
        user_set = User.objects.filter(customuser__person_cluster=filter_person_cluster)
        bilder = Bilder2.objects.filter(org=org, user__in=user_set).order_by('-date_created')
    elif filter_user:
        bilder = Bilder2.objects.filter(org=org, user=filter_user).order_by('-date_created')
    else:
        bilder = Bilder2.objects.filter(org=org).order_by('-date_created')

    # Prefetch related data for better performance
    bilder = bilder.prefetch_related(
        'comments__user',
        'reactions__user',
        'bildergallery2_set'
    ).select_related('user')

    if limit:
        bilder = bilder[:limit]

    gallery_images = []
    for bild in bilder:
        gallery_images.append({
            bild: BilderGallery2.objects.filter(bilder=bild)
        })
    return gallery_images


def get_posts(org, filter_user=None, filter_person_cluster=None, limit=None):
    """
    Retrieve posts, optionally filtered by organization.
    
    Args:
        org: The organization object
        limit (int, optional): Maximum number of posts to return. Defaults to None.
    
    Returns:
        list: List of dictionaries containing posts and their metadata
    """
    posts = Post2.objects.filter(org=org).order_by('-date_updated')
    if filter_user and filter_person_cluster:
        posts = posts.filter(Q(user=filter_user) | Q(person_cluster=filter_person_cluster))
    elif filter_user:
        posts = posts.filter(user=filter_user)
    elif filter_person_cluster:
        posts = posts.filter(person_cluster=filter_person_cluster)
    if limit:
        posts = posts[:limit]
    return posts


def check_organization_context(request, context=None):
    """
    Enhance the template context with organization-specific settings.
    
    Args:
        request: The HTTP request object
        context (dict, optional): Existing context dictionary. Defaults to empty dict if None.
    
    Returns:
        dict: The enhanced context dictionary with organization-specific settings
    """
    if context is None:
        context = {}

    # Check if user is authenticated and has a custom user profile
    if not request.user.is_authenticated or not hasattr(request.user, 'role'):
        return context

    # Add organization-specific template settings if user is an organization
    if request.user.role == 'O':
        context.update({
            'extends_base': org_base_template,
            'is_org': True
        })
    elif request.user.role == 'T':
        context.update({
            'extends_base': team_base_template,
            'is_team': True
        })
    elif request.user.role == 'F':
        context.update({
            'extends_base': fw_base_template,
            'is_freiwilliger': True
        })
    elif request.user.role == 'B':
        context.update({
            'extends_base': bw_base_template,
            'is_bewerber': True
        })
    elif request.user.role == 'E':
        context.update({
            'extends_base': ehemalige_base_template,
            'is_ehemalige': True
        })

    return context

# Basic Views
def datenschutz(request):
    """Render the privacy policy page."""
    return render(request, 'datenschutz.html')


def serve_logo(request, org_id):
    """
    Serve organization logo images.
    
    Args:
        request: The HTTP request object
        image_name (str): Name of the logo image file
        
    Returns:
        HttpResponse: Response containing the logo image
        HttpResponseNotFound: If the image doesn't exist
    """
    try:
        org = Organisation.objects.get(id=org_id)
    except Organisation.DoesNotExist:
        return HttpResponseNotFound('Organisation nicht gefunden')

    if not org.logo:
        return HttpResponseNotFound('Logo nicht gefunden')

    try:
        # File metadata for caching
        file_path = org.logo.path
        stat = os.stat(file_path)
        last_modified = datetime.fromtimestamp(stat.st_mtime, tz=dt_timezone.utc)
        etag_base = f"{stat.st_ino}-{stat.st_size}-{int(stat.st_mtime)}"
        etag = hashlib.md5(etag_base.encode('utf-8')).hexdigest()

        # Conditional GET: ETag
        if_none_match = request.META.get('HTTP_IF_NONE_MATCH')
        if if_none_match and if_none_match.strip('"') == etag:
            not_modified = HttpResponse(status=304)
            not_modified['ETag'] = f'"{etag}"'
            not_modified['Cache-Control'] = 'public, max-age=86400, immutable'
            not_modified['Last-Modified'] = last_modified.strftime('%a, %d %b %Y %H:%M:%S GMT')
            return not_modified

        # Conditional GET: Last-Modified
        if_modified_since = request.META.get('HTTP_IF_MODIFIED_SINCE')
        if if_modified_since:
            try:
                ims_dt = datetime.strptime(if_modified_since, '%a, %d %b %Y %H:%M:%S GMT')
                # If the resource has not changed since the date sent by the client
                if last_modified <= ims_dt:
                    not_modified = HttpResponse(status=304)
                    not_modified['ETag'] = f'"{etag}"'
                    not_modified['Cache-Control'] = 'public, max-age=86400, immutable'
                    not_modified['Last-Modified'] = last_modified.strftime('%a, %d %b %Y %H:%M:%S GMT')
                    return not_modified
            except Exception:
                pass

        # Guess content type
        mime_type = mimetypes.guess_type(file_path)[0] or 'application/octet-stream'

        with open(file_path, 'rb') as img_file:
            response = HttpResponse(img_file.read(), content_type=mime_type)
            response['Content-Disposition'] = f'inline; filename="{os.path.basename(org.logo.name)}"'
            response['ETag'] = f'"{etag}"'
            response['Last-Modified'] = last_modified.strftime('%a, %d %b %Y %H:%M:%S GMT')
            response['Cache-Control'] = 'public, max-age=86400, immutable'
            return response
    except FileNotFoundError:
        return HttpResponseNotFound('Bild nicht gefunden')

@login_required
@required_person_cluster('bilder')
def serve_bilder(request, image_id=None):
    """
    Serve gallery images.
    
    Args:
        request: The HTTP request object
        image_id (int): ID of the gallery image
        
    Returns:
        HttpResponse: Response containing the image
        HttpResponseNotFound: If the image doesn't exist
        HttpResponseNotAllowed: If user doesn't have permission
    """
    
    try:
        image_id = int(image_id)
        bild = BilderGallery2.objects.get(id=image_id, org=request.user.org)
    except (ValueError, BilderGallery2.DoesNotExist):
        return HttpResponseNotFound('Bild nicht gefunden')
    
    return get_bild(bild.image.path, bild.bilder.titel)

@login_required
@required_person_cluster('bilder')
def serve_small_bilder(request, image_id):
    """
    Serve small (thumbnail) versions of gallery images.
    
    Args:
        request: The HTTP request object
        image_id (int): ID of the gallery image
        
    Returns:
        HttpResponse: Response containing the small image
        HttpResponseNotFound: If the image doesn't exist
        HttpResponseNotAllowed: If user doesn't have permission
    """
    try:
        bild = BilderGallery2.objects.get(id=image_id, org=request.user.org)
    except BilderGallery2.DoesNotExist:
        return HttpResponseNotFound('Bild nicht gefunden')

    if not bild.small_image:
        return serve_bilder(request, image_id)

    return get_bild(bild.small_image.path, bild.bilder.titel)

@login_required
@required_person_cluster('dokumente')
def serve_dokument(request, dokument_id):
    """
    Serve document files with proper content type handling.
    
    Args:
        request: The HTTP request object
        dokument_id (int): ID of the document
        
    Returns:
        HttpResponse: Response containing the document
        HttpResponseNotFound: If document doesn't exist
        HttpResponseNotAllowed: If user doesn't have permission
    """
    img = request.GET.get('img', None)
    download = request.GET.get('download', None)
    
    try:
        dokument_id = int(dokument_id)
        dokument = Dokument2.objects.get(id=dokument_id)
        
        if not dokument.org == request.user.org:
            return HttpResponseNotAllowed('Nicht erlaubt')
        
        doc_path = dokument.dokument.path
        if not os.path.exists(doc_path) or not dokument.dokument:
            return HttpResponseNotFound('Dokument nicht gefunden' + doc_path)
    except ValueError:
        return HttpResponseNotFound('Ungültige Dokument-ID')
    except Dokument2.DoesNotExist:
        return HttpResponseNotFound('Dokument nicht gefunden')

    

    mimetype = get_mimetype(doc_path)
    
    # Handle image documents
    if mimetype and mimetype.startswith('image') and not download:
        return get_bild(doc_path, dokument.dokument.name)

    # Handle preview images
    if img and not download:
        img_path = dokument.get_preview_image()
        if img_path:
            return get_bild(img_path, img_path.split('/')[-1])

    # Serve document as download
    with open(doc_path, 'rb') as file:
        if mimetype == 'application/pdf' and not download:
            response = HttpResponse(file.read(), content_type='application/pdf')
            response['Content-Disposition'] = f'inline; filename="{dokument.dokument.name}"'
            response['Content-Security-Policy'] = "frame-ancestors 'self'"
            return response
        # For PDFs, display in browser instead of downloading
        response = HttpResponse(file.read(), content_type=mimetype or 'application/octet-stream')
        response['Content-Disposition'] = f'attachment; filename="{dokument.dokument.name}"'
        return response

@login_required
@required_person_cluster('bilder')
def bilder(request):
    
    error = None

    if request.user.role == 'O':
        from ORG.views import get_person_cluster
        person_cluster = get_person_cluster(request)
        if person_cluster:
            if person_cluster.bilder:
                gallery_images = get_bilder(request.user.org, filter_person_cluster=person_cluster)
            else:
                error = f'{person_cluster.name} hat keine Bilder-Funktion aktiviert'
                gallery_images = []
        else:
            gallery_images = get_bilder(request.user.org)

    else:
        gallery_images = get_bilder(request.user.org)

    context={'gallery_images': gallery_images, 'error': error}

    context = check_organization_context(request, context)

    return render(request, 'bilder.html', context=context)

@login_required
@required_person_cluster('bilder')
def bild(request):
    if request.method == 'POST':
        bilder_form = BilderForm(request.POST, user=request.user, org=request.user.org)
        images = request.FILES.getlist('image')

        if bilder_form.is_valid() and len(images) > 0:
            # Pass images to the form's save method
            bilder, created = bilder_form.save(images=images)
            
            # Enqueue email sending task only for new submissions
            if created:
                try:
                    send_image_uploaded_email_task.apply_async(args=[bilder.id], countdown=5)
                except Exception as e:
                    logging.error(f"Error scheduling image uploaded email task: {e}")

            messages.success(request, _('Bilder erfolgreich hochgeladen'))
            return redirect('bilder')
        else:
            if not images:
                messages.error(request, _('Bitte wählen Sie mindestens ein Bild aus'))
            else:
                messages.error(request, _('Bitte korrigieren Sie die Fehler im Formular.') + ' ' + str(bilder_form.errors))
    else:
        bilder_form = BilderForm(initial={'submission_key': uuid.uuid4()}, user=request.user, org=request.user.org)

    bilder_gallery_form = BilderGalleryForm()
    
    context = {
        'bilder_form': bilder_form,
        'bilder_gallery_form': bilder_gallery_form,
    }

    context = check_organization_context(request, context)

    return render(request, 'bild.html', context=context)

@login_required
@required_person_cluster('bilder')
def remove_bild(request):
    gallery_image_id = request.GET.get('galleryImageId', None)
    bild_id = request.GET.get('bildId', None)

    if not gallery_image_id and not bild_id:
        messages.error(request, 'Kein Bild gefunden')
        return redirect('profil')

    try:
        gallery_image = BilderGallery2.objects.get(id=gallery_image_id, org=request.user.org)
    except BilderGallery2.DoesNotExist:
        messages.error(request, 'Bild nicht gefunden')
        return redirect('profil')

    if gallery_image.bilder.user != request.user:
        messages.error(request, 'Nicht erlaubt')
        return redirect('profil')

    # Check if this is the last image in the gallery
    related_gallery_images = BilderGallery2.objects.filter(bilder=gallery_image.bilder)
    if related_gallery_images.count() == 1:
        # Delete the parent Bilder object if this is the last image
        gallery_image.bilder.delete()
    else:
        # Otherwise just delete this specific image
        gallery_image.delete()

    messages.success(request, 'Bild erfolgreich gelöscht')

    return redirect('profil')

@login_required
@required_person_cluster('bilder')
def remove_bild_all(request):
    bild_id = request.GET.get('bild_id', None)
    if not bild_id:
        messages.error(request, 'Kein Bild gefunden')
        return redirect('profil')
    
    try:
        bild = Bilder2.objects.get(id=bild_id, org=request.user.org, user=request.user)
    except Bilder2.DoesNotExist:
        messages.error(request, 'Bild nicht gefunden')
        return redirect('profil')

    bilder_gallery = BilderGallery2.objects.filter(bilder=bild)
    for bild_gallery in bilder_gallery:
        bild_gallery.delete()
    bild.delete()
    messages.success(request, 'Alle Bilder erfolgreich gelöscht')
    return redirect('profil')

@login_required
@required_person_cluster('bilder')
def add_comment_to_bild(request, bild_id):
    """Add a comment to a Bilder2 object."""
    if request.method != 'POST':
        messages.error(request, 'Ungültige Anfrage')
        return redirect('bilder')
    
    try:
        from .models import BilderComment, BilderGallery2
        bild = Bilder2.objects.get(id=bild_id, org=request.user.org)
        comment_text = request.POST.get('comment', '').strip()
        
        if not comment_text:
            messages.error(request, 'Kommentar darf nicht leer sein')
            gallery_image = BilderGallery2.objects.filter(bilder=bild).first()
            if gallery_image:
                return redirect('image_detail', image_id=bild.id)
            return redirect('bilder')
        
        if len(comment_text) > 500:
            messages.error(request, 'Kommentar ist zu lang (max. 500 Zeichen)')
            gallery_image = BilderGallery2.objects.filter(bilder=bild).first()
            if gallery_image:
                return redirect('image_detail', image_id=bild.id)
            return redirect('bilder')
        
        BilderComment.objects.create(
            bilder=bild,
            user=request.user,
            org=request.user.org,
            comment=comment_text
        )
        
        return redirect('image_detail', image_id=bild.id)
        
    except Bilder2.DoesNotExist:
        messages.error(request, 'Bild nicht gefunden')
        return redirect('bilder')
    except Exception as e:
        messages.error(request, f'Fehler beim Hinzufügen des Kommentars: {str(e)}')
        return redirect('bilder')

@login_required
@required_person_cluster('bilder')
def remove_comment_from_bild(request, comment_id):
    """Remove a comment from a Bilder2 object."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method'}, status=405)
    
    try:
        from .models import BilderComment, BilderGallery2
        comment = BilderComment.objects.get(id=comment_id, org=request.user.org)
        
        # Check permissions - user can only delete their own comments, or admins can delete any
        if comment.user != request.user and request.user.role != 'O':
            messages.error(request, 'Keine Berechtigung zum Löschen dieses Kommentars')
            gallery_image = BilderGallery2.objects.filter(bilder=comment.bilder).first()
            if gallery_image:
                return redirect('image_detail', image_id=bild.id)
            return redirect('bilder')
        
        bild = comment.bilder
        comment.delete()
        
        messages.success(request, 'Kommentar wurde gelöscht')
        # Redirect to image detail page
        gallery_image = BilderGallery2.objects.filter(bilder=bild).first()
        if gallery_image:
            return redirect('image_detail', image_id=bild.id)
        else:
            return redirect('bilder')
        
    except BilderComment.DoesNotExist:
        messages.error(request, 'Kommentar nicht gefunden')
        return redirect('bilder')
    except Exception as e:
        messages.error(request, f'Fehler beim Löschen des Kommentars: {str(e)}')
        return redirect('bilder')

def _validate_emoji(emoji):
    """Validate if the provided emoji is allowed."""
    from .models import BilderReaction
    valid_emojis = [choice[0] for choice in BilderReaction.EMOJI_CHOICES]
    return emoji in valid_emojis

def _handle_reaction_toggle(bild, user, emoji):
    """Handle the logic for toggling a reaction."""
    from .models import BilderReaction
    
    existing_reaction = BilderReaction.objects.filter(bilder=bild, user=user).first()
    
    if existing_reaction:
        if existing_reaction.emoji == emoji:
            # Remove existing reaction (toggle off)
            existing_reaction.delete()
            return 'removed'
        else:
            # Update to new emoji
            existing_reaction.emoji = emoji
            existing_reaction.date_created = datetime.now()
            existing_reaction.save()
            return 'changed'
    else:
        # Create new reaction
        BilderReaction.objects.create(
            bilder=bild,
            user=user,
            emoji=emoji,
            org=user.org
        )
        return 'added'

@login_required
@required_person_cluster('bilder')
def toggle_reaction_to_bild(request, bild_id, emoji):
    """Toggle an emoji reaction on a Bilder2 object. Each user can only have one reaction per image."""
    if request.method != 'GET':
        messages.error(request, 'Ungültige Anfrage')
        return redirect('bilder')
    
    # Validate emoji
    if not _validate_emoji(emoji):
        messages.error(request, 'Ungültiges Emoji')
        return redirect('bilder')
    
    try:
        # Get the bild
        bild = Bilder2.objects.get(id=bild_id, org=request.user.org)

        # Handle the reaction toggle
        action = _handle_reaction_toggle(bild, request.user, emoji)
        
        return JsonResponse({
            'success': True,
            'bild_id': bild.id,
            'emoji': emoji,
            'action': action
        })
        
    except Bilder2.DoesNotExist:
        messages.error(request, 'Bild nicht gefunden')
        return redirect('bilder')
    except Exception as e:
        messages.error(request, 'Reaktion konnte nicht verarbeitet werden')
        return redirect('bilder')

@login_required
@required_person_cluster('bilder')
def get_bild_reactions(request, bild_id):
    """Get detailed reaction information for a specific image."""
    if request.method != 'GET':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        # Get the bild
        bild = Bilder2.objects.get(id=bild_id, org=request.user.org)
        
        # Get all reactions with user details
        reactions_data = bild.get_all_reactions_with_users()
        
        # Format the response
        response_data = {
            'success': True,
            'bild_id': bild.id,
            'bild_title': bild.titel,
            'reactions': reactions_data
        }
        
        return JsonResponse(response_data)
        
    except Bilder2.DoesNotExist:
        return JsonResponse({'error': 'Bild nicht gefunden'}, status=404)
    except Exception as e:
        return JsonResponse({'error': 'Fehler beim Laden der Reaktionen'}, status=500)

@login_required
@required_person_cluster('bilder')
def image_detail(request, image_id):
    """Display detailed view of a single image with navigation and interactions."""
    try:
        # Get the specific gallery image
        current_image = Bilder2.objects.get(id=image_id, org=request.user.org)
        bilder_gallery = BilderGallery2.objects.filter(bilder=current_image)
        
        # Get size of all images - pass to client for smart loading
        size_of_all_images = current_image.get_size()
        
        context = {
            'bild': current_image,
            'bilder_gallery': bilder_gallery,
            'size_of_all_images': size_of_all_images
        }

        context = check_organization_context(request, context)
        return render(request, 'image_detail.html', context)
    
    except Bilder2.DoesNotExist:
        messages.error(request, 'Bild nicht gefunden')
        return redirect('bilder')
        
    except BilderGallery2.DoesNotExist:
        messages.error(request, 'Bild nicht gefunden')
        return redirect('bilder')
    

def edit_bild(request, bild_id):
    try:
        bild = Bilder2.objects.get(id=bild_id, org=request.user.org, user=request.user)
        if request.method == 'POST':
            titel = request.POST.get('titel').strip()
            beschreibung = request.POST.get('beschreibung').strip()
            if titel == '':
                messages.error(request, 'Titel darf nicht leer sein')
                return redirect('image_detail', image_id=bild_id)
            bild.titel = titel
            bild.beschreibung = beschreibung
            bild.save()
    except Bilder2.DoesNotExist:
        messages.error(request, 'Bild nicht gefunden')
    except Exception as e:
        messages.error(request, f'Fehler beim Bearbeiten des Bildes: {str(e)}')
    return redirect(request.META.get('HTTP_REFERER'))

@login_required
@required_role('OT')
# @filter_person_cluster
def download_bild_as_zip(request, id):
    try:
        bild = Bilder2.objects.get(pk=id, org=request.user.org)
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zipf:
            for i, bild_gallery in enumerate(BilderGallery2.objects.filter(bilder=bild)):
                zipf.write(bild_gallery.image.path, f"{bild.user.username}-{bild.titel.replace(' ', '_')}-{bild.date_created.strftime('%Y-%m-%d')}_{i}{os.path.splitext(bild_gallery.image.path)[1]}")
        zip_buffer.seek(0)
        response = HttpResponse(zip_buffer, content_type='application/zip')
        response['Content-Disposition'] = f'attachment; filename="{bild.user.username}_{bild.titel}_{bild.date_created.strftime("%Y-%m-%d")}.zip"'
        return response
    except Bilder2.DoesNotExist:
        return HttpResponseNotFound('Nicht gefunden')


@login_required
@required_person_cluster('dokumente')
def dokumente(request, ordner_id=None):
    folder_structure = []

    if request.user.role == 'O':
        from ORG.views import get_person_cluster
        person_cluster_typ = get_person_cluster(request)
    else:
        person_cluster_typ = request.user.person_cluster

    ordners = []
    error = None

    if person_cluster_typ:
        if person_cluster_typ.dokumente:
            ordners = Ordner2.objects.filter(org=request.user.org).filter(Q(typ=None) | Q(typ=person_cluster_typ)).order_by('color', 'ordner_name')
        else:
            error = f'{person_cluster_typ.name} hat keine Dokumenten-Funktion aktiviert'
    else:
        ordners = Ordner2.objects.filter(org=request.user.org).order_by('color', 'ordner_name')
    
    for ordner in ordners:
        folder_structure.append({
            'ordner': ordner,
            'dokumente': Dokument2.objects.filter(org=request.user.org, ordner=ordner).order_by('-date_created')
        })

    colors = DokumentColor2.objects.all()

    context = {
        'ordners': ordners,
        'folder_structure': folder_structure,
        'ordner_id': ordner_id,
        'person_clusters': PersonCluster.objects.filter(org=request.user.org, dokumente=True).order_by('name'),
        'colors': colors,
        'error': error
    }

    context = check_organization_context(request, context)

    return render(request, 'dokumente.html', context=context)

@login_required
@required_person_cluster('dokumente')
def add_dokument(request):
    if request.method != 'POST':
        return redirect('dokumente')
        
    dokument_id = request.POST.get('dokument_id')
    titel = request.POST.get('titel')
    beschreibung = request.POST.get('beschreibung')
    link = request.POST.get('link')
    darf_bearbeiten = request.POST.getlist('darf_bearbeiten')
    darf_bearbeiten = PersonCluster.objects.filter(id__in=darf_bearbeiten)
    file = request.FILES.get('dokument')
    
    if dokument_id and dokument_id != '':
        try:
            dokument = Dokument2.objects.get(id=dokument_id, org=request.user.org)
        except Dokument2.DoesNotExist:
            messages.error(request, 'Dokument nicht gefunden')
            return redirect('dokumente')
    else:
        try:
            ordner = Ordner2.objects.get(id=request.POST.get('ordner'))
            dokument = Dokument2.objects.create(
                org=request.user.org,
                ordner=ordner,
                date_created=datetime.now()
            )
        except Ordner2.DoesNotExist:
            messages.error(request, 'Ordner nicht gefunden')
            return redirect('dokumente')
        except Exception as e:
            messages.error(request, f'Fehler beim Erstellen des Dokuments: {str(e)}')
            return redirect('dokumente')
    
    dokument.titel = titel
    dokument.beschreibung = beschreibung
    dokument.link = link
    if file:
        dokument.dokument = file    
    if request.user.role == 'O':
        dokument.darf_bearbeiten.set(darf_bearbeiten)
    dokument.save()

    return redirect('dokumente', ordner_id=dokument.ordner.id)
    

@login_required
@required_person_cluster('dokumente')
@required_role('O')
def add_ordner(request):
    if request.method == 'POST':
        ordner_id = request.POST.get('ordner_id')
        ordner_name = request.POST.get('ordner_name')
        person_cluster_ids = request.POST.getlist('ordner_person_cluster')
        color_id = request.POST.get('color')
        
        # Validate required fields
        if not ordner_name:
            messages.error(request, 'Ordnername ist erforderlich.')
            return redirect('dokumente')
        
        # Get the PersonenCluster instance if typ_id is provided
        person_clusters = None
            
        try:
            if person_cluster_ids:
                person_clusters = PersonCluster.objects.filter(id__in=person_cluster_ids)
            
            color = None
            if color_id:
                color = DokumentColor2.objects.get(id=color_id)
                
            if ordner_id:
                ordner = Ordner2.objects.get(id=ordner_id, org=request.user.org)
            elif ordner_name:
                ordner = Ordner2.objects.create(
                    org=request.user.org, 
                    ordner_name=ordner_name,
                    color=color
                )
            else:
                messages.error(request, 'Kein Ordnername oder Ordner-ID angegeben.')
                return redirect('dokumente')
            
            ordner.ordner_name = ordner_name
            ordner.typ.set(person_clusters or [])
            ordner.color = color
            ordner.save()    
            
        except PersonCluster.DoesNotExist:
            messages.error(request, 'Ausgewählte Benutzergruppe existiert nicht.')
            return redirect('dokumente')
        except DokumentColor2.DoesNotExist:
            messages.error(request, 'Ausgewählte Farbe existiert nicht.')
            return redirect('dokumente')
        except Exception as e:
            messages.error(request, f'Fehler beim Erstellen des Ordners: {str(e)}')
            return redirect('dokumente')

    return redirect('dokumente')

@login_required
@required_person_cluster('dokumente')
def remove_dokument(request):
    if request.method == 'POST':
        dokument_id = request.POST.get('dokument_id')
        try:
            dokument = Dokument2.objects.get(id=dokument_id, org=request.user.org)
            if request.user.role == 'O' or request.user.person_cluster in dokument.darf_bearbeiten.all():
                dokument.delete()
            else:
                messages.error(request, 'Dokument kann nicht gelöscht werden, da du nicht der Ersteller bist.')
        except Dokument2.DoesNotExist:
            pass

    return redirect('dokumente')

@login_required
@required_person_cluster('dokumente')
def remove_ordner(request):
    if request.method == 'POST':
        ordner_id = request.POST.get('ordner_id')
        try:
            ordner = Ordner2.objects.get(id=ordner_id, org=request.user.org)
            # Only delete if folder is empty
            if not Dokument2.objects.filter(ordner=ordner).exists():
                ordner.delete()
                messages.success(request, 'Ordner wurde gelöscht.')
            else:
                messages.error(request, f'Ordner {ordner.ordner_name} konnte nicht gelöscht werden, da er nicht leer ist.')
        except Ordner2.DoesNotExist:
            pass

    return redirect('dokumente')

@login_required
def update_profil_picture(request):
    if request.method == 'POST' and request.FILES.get('profil_picture'):
        try:
            custom_user = request.user.customuser
            # Delete old profil picture if it exists
            if custom_user.profil_picture:
                custom_user.profil_picture.delete()
            
            custom_user.profil_picture = request.FILES['profil_picture']
            custom_user.save()
            custom_user.create_small_image()
            messages.success(request, 'Profilbild wurde erfolgreich aktualisiert.')
        except Exception as e:
            messages.error(request, f'Fehler beim Aktualisieren des Profilbildes: {str(e)}')
    
    return redirect('profil')

@login_required
def serve_profil_picture(request, user_id):
    requested_user = User.objects.get(id=user_id)

    def _serve_cached_image(file_path, download_name):
        stat = os.stat(file_path)
        last_modified = datetime.fromtimestamp(stat.st_mtime, tz=dt_timezone.utc)
        etag_base = f"{stat.st_ino}-{stat.st_size}-{int(stat.st_mtime)}"
        etag = hashlib.md5(etag_base.encode('utf-8')).hexdigest()

        if_none_match = request.META.get('HTTP_IF_NONE_MATCH')
        if if_none_match and if_none_match.strip('"') == etag:
            not_modified = HttpResponse(status=304)
            not_modified['ETag'] = f'"{etag}"'
            not_modified['Cache-Control'] = 'public, max-age=86400, immutable'
            not_modified['Last-Modified'] = last_modified.strftime('%a, %d %b %Y %H:%M:%S GMT')
            return not_modified

        if_modified_since = request.META.get('HTTP_IF_MODIFIED_SINCE')
        if if_modified_since:
            try:
                ims_dt = datetime.strptime(if_modified_since, '%a, %d %b %Y %H:%M:%S GMT')
                if last_modified <= ims_dt:
                    not_modified = HttpResponse(status=304)
                    not_modified['ETag'] = f'"{etag}"'
                    not_modified['Cache-Control'] = 'public, max-age=86400, immutable'
                    not_modified['Last-Modified'] = last_modified.strftime('%a, %d %b %Y %H:%M:%S GMT')
                    return not_modified
            except Exception:
                pass

        mime_type = mimetypes.guess_type(file_path)[0] or 'application/octet-stream'
        with open(file_path, 'rb') as img_file:
            response = HttpResponse(img_file.read(), content_type=mime_type)
            response['Content-Disposition'] = f'inline; filename="{os.path.basename(download_name)}"'
            response['ETag'] = f'"{etag}"'
            response['Last-Modified'] = last_modified.strftime('%a, %d %b %Y %H:%M:%S GMT')
            response['Cache-Control'] = 'public, max-age=86400, immutable'
            return response

    if requested_user.org != request.user.org:
        return HttpResponseForbidden()
    
    if not requested_user.customuser.profil_picture:
        # Use Django's static file finder to get the correct path with hash
        from django.contrib.staticfiles.finders import find
        from django.contrib.staticfiles.storage import staticfiles_storage
        
        # Try to find the default image using the static file finder
        default_img_path = find('img/default_img.png')
        if default_img_path:
            return _serve_cached_image(default_img_path, 'default_img.png')
        else:
            # If the file is not found, try to serve it from the staticfiles storage
            try:
                # Get the hashed filename from staticfiles storage
                hashed_path = staticfiles_storage.path('img/default_img.png')
                if os.path.exists(hashed_path):
                    return _serve_cached_image(hashed_path, 'default_img.png')
                else:
                    # Last resort: redirect to the static URL
                    default_img_url = staticfiles_storage.url('img/default_img.png')
                    return HttpResponseRedirect(default_img_url)
            except Exception as e:
                # Return a simple 404 or placeholder
                return HttpResponseNotFound('Default profile picture not found')

    return _serve_cached_image(requested_user.customuser.profil_picture.path, requested_user.customuser.profil_picture.name)


def unsubscribe_mail_notifications(request, user_id, auth_key):
    try:
        custom_user = CustomUser.objects.get(user__id=user_id)

        # Check if the auth key matches or the user is already authenticated as this user
        if custom_user.mail_notifications_unsubscribe_auth_key == auth_key or request.user.id == user_id:
            if request.GET.get('value') == 'true':
                custom_user.mail_notifications = True
                messages.success(request, 'Mail-Benachrichtigungen wurden aktiviert')
            else:
                custom_user.mail_notifications = False
                messages.success(request, 'Mail-Benachrichtigungen wurden deaktiviert')
        else:
            messages.error(request, 'Ungültige Abmelde-URL')
        
        custom_user.save()

    except CustomUser.DoesNotExist:
        messages.error(request, 'Benutzer nicht gefunden')
    return redirect('profil')

@login_required
def view_profil(request, user_id=None):
    if request.POST:
        attribut = request.POST.get('attribut')
        value = request.POST.get('value')
        ProfilUser2.objects.create(
            org=request.user.org,
            user=request.user,
            attribut=attribut,
            value=value
        )
        return redirect('profil')

    this_user = False
    if not user_id or user_id == request.user.id:
        user_id = request.user.id
        this_user = True
    
    try:
        user = User.objects.get(id=user_id, customuser__org=request.user.org)
    except User.DoesNotExist:
        messages.error(request, 'Nicht gefunden')
        return redirect('profil')

    if request.method == 'POST':
        profil_user_form = ProfilUserForm(request.POST)
        if profil_user_form.is_valid():
            profil_user = profil_user_form.save(commit=False)
            profil_user.user = request.user
            profil_user.org = request.user.org
            profil_user.save()
            return redirect('profil')

    profil_users = ProfilUser2.objects.filter(user=user).order_by('attribut')
    user_attributes = UserAttribute.objects.filter(user=user).order_by('attribute__name') if this_user or request.user.role == 'O' else []
    gallery_images = get_bilder(request.user.org, user)

    ampel_of_user = None
    if this_user or request.user.role in 'OT':
        ampel_of_user = Ampel2.objects.filter(user=user).order_by('-date').first()

    profil_user_form = ProfilUserForm()

    try:
        freiwilliger = Freiwilliger.objects.get(user=user)
    except Freiwilliger.DoesNotExist:
        freiwilliger = None

    posts = get_posts(request.user.org, filter_user=user)

    context = {
        'freiwilliger': freiwilliger,
        'user': user,
        'profil_users': profil_users,
        'profil_user_form': profil_user_form,
        'this_user': this_user,
        'ampel_of_user': ampel_of_user,
        'gallery_images': gallery_images,
        'posts': posts,
        'user_attributes': user_attributes
    }

    context = check_organization_context(request, context)

    return render(request, 'profil.html', context=context)

@login_required
def remove_profil_attribut(request, profil_id):
    profil_user = ProfilUser2.objects.get(id=profil_id)
    if profil_user.user == request.user:
        profil_user.delete()
    return redirect('profil')

@login_required
def feedback(request):
    if request.method == 'POST':
        feedback_form = FeedbackForm(request.POST)
        if feedback_form.is_valid():
            feedback = feedback_form.save(commit=False)
            if not feedback_form.cleaned_data['anonymous']:
                feedback.user = request.user
                feedback.save()
            messages.success(request, 'Feedback erfolgreich gesendet')
            return redirect('index_home')
    feedback_form = FeedbackForm()

    import json

    with open('FWMsg/.secrets.json', 'r') as f:
        secrets = json.load(f)
    feedback_email = secrets['feedback_email']

    context = {
        'form': feedback_form,
        'feedback_email': feedback_email
    }
    context = check_organization_context(request, context)
    return render(request, 'feedback.html', context=context)

@login_required
@required_person_cluster('calendar')
def kalender(request):
    calendar_events = get_calendar_events(request)

    context = {
        'calendar_events': calendar_events
    }
    context = check_organization_context(request, context)
    return render(request, 'kalender.html', context=context)

@login_required
@required_person_cluster('calendar')
def kalender_event(request, kalender_id):
    if request.user.role == 'O':
        kalender_event = KalenderEvent.objects.get(id=kalender_id, org=request.user.org)
    else:
        kalender_event = KalenderEvent.objects.get(id=kalender_id, org=request.user.org, user__in=[request.user])
    context = {
        'kalender_event': kalender_event
    }
    context = check_organization_context(request, context)
    return render(request, 'kalender_event.html', context=context)

@login_required
@required_person_cluster('calendar')
def get_calendar_events(request):
    calendar_events = []
    
    for user_aufgabe in UserAufgaben.objects.filter(user=request.user):
        color = '#dc3545'  # Bootstrap danger color to match the theme
        if user_aufgabe.erledigt:
            color = '#198754'  # Bootstrap success color
        elif user_aufgabe.pending:
            color = '#ffc107'  # Bootstrap warning color
        elif user_aufgabe.faellig and user_aufgabe.faellig > datetime.now().date():
            color = '#0d6efd'  # Bootstrap primary color

        calendar_events.append({
            'title': user_aufgabe.aufgabe.name,
            'start': user_aufgabe.faellig.strftime('%Y-%m-%d') if user_aufgabe.faellig else '',
            'url': reverse('aufgaben_detail', args=[user_aufgabe.id]),
            'backgroundColor': color,
            'borderColor': color,
            'textColor': '#000'
        })

    if request.user.is_staff or request.user.role == 'O':
        custom_users = CustomUser.objects.filter(org=request.user.org)
    elif request.user.role == 'T':
        try:
            team = Team.objects.get(user=request.user)
            laender_ids = team.land.values_list('id', flat=True)
            freiwillige_users = Freiwilliger.objects.filter(einsatzland2__in=laender_ids).values_list('user', flat=True)
            custom_users = CustomUser.objects.filter(org=request.user.org, user__in=freiwillige_users)
        except Team.DoesNotExist:
            custom_users = CustomUser.objects.none()
    else:
        custom_users = CustomUser.objects.filter(org=request.user.org, person_cluster=request.user.person_cluster)

    birthday_events = custom_users.filter(geburtsdatum__isnull=False)
    for birthday_event in birthday_events:
        # add two times to the calendar, one for the birthday this year and one for the birthday next year
        for i in range(5):
            birthday = birthday_event.geburtsdatum.replace(year=datetime.now().year + i)
            calendar_events.append({
                'title': f'Geburtstag: {birthday_event.user.first_name} {birthday_event.user.last_name}',
                'start': birthday.strftime('%Y-%m-%d') if birthday else '',
                'url': reverse('profil', args=[birthday_event.user.id]),
                'backgroundColor': '#ff69b4', # Hot pink - cheerful color for birthdays
                'borderColor': '#ff69b4',
                'textColor': '#fff'
            })
        
    if request.user.role == 'O':
        kalender_events = KalenderEvent.objects.filter(org=request.user.org)
    else:
        kalender_events = KalenderEvent.objects.filter(org=request.user.org).filter(user__in=[request.user])
        
    for kalender_event in kalender_events:
        calendar_events.append({
            'title': kalender_event.title,
            'start': kalender_event.start.astimezone(timezone.get_current_timezone()).strftime('%Y-%m-%d %H:%M') if kalender_event.start else '',
            'end': kalender_event.end.astimezone(timezone.get_current_timezone()).strftime('%Y-%m-%d %H:%M') if kalender_event.end else '',
            'url': reverse('kalender_event', args=[kalender_event.id]),
            'backgroundColor': '#000',
            'borderColor': '#000',
            'textColor': '#fff',
            'extendedProps': {
                'location': kalender_event.location,
                'description': kalender_event.description
            }
        })
            
    return JsonResponse(calendar_events, safe=False)

@login_required
@required_person_cluster('notfallkontakt')
def notfallkontakte(request):

    if request.method == 'POST':
        form = AddNotfallkontaktForm(request.POST)
        if form.is_valid():
            form.instance.org = request.user.org
            form.instance.user = request.user
            form.save()
            return redirect('notfallkontakte')
        else:
            messages.error(request, 'Fehler beim Hinzufügen des Notfallkontakts')
    form = AddNotfallkontaktForm()
    notfallkontakte = Notfallkontakt2.objects.filter(user=request.user)
    context = {
        'form': form,
        'notfallkontakte': notfallkontakte
    }
    context = check_organization_context(request, context)
    return render(request, 'notfallkontakte.html', context=context)


@login_required
@required_person_cluster('ampel')
def ampel(request):
    if request.method == 'POST':
        form = AddAmpelmeldungForm(request.POST, user=request.user, org=request.user.org)
        if form.is_valid():
            ampel_object, created = form.save()
            if created:
                from ORG.tasks import send_ampel_email_task
                send_ampel_email_task.s(ampel_object.id).apply_async(countdown=10)

            s = form.cleaned_data['status']
            msg_text = 'Ampel erfolgreich auf ' + (
                'Grün' if s == 'G' else 'Rot' if s == 'R' else 'Gelb' if s == 'Y' else 'error') + ' gesetzt'
            messages.success(request, msg_text)
            return redirect('fw_home')
        else:
            # Form has validation errors, show them to user
            messages.error(request, 'Bitte korrigieren Sie die Fehler im Formular.' + str(form.errors))
    else:
        form = AddAmpelmeldungForm(initial={'submission_key': uuid.uuid4()}, user=request.user, org=request.user.org)

    last_ampel = Ampel2.objects.filter(user=request.user).order_by('-date').first()
    context = {
        'last_ampel': last_ampel,
        'submission_key': form.initial.get('submission_key') if hasattr(form, 'initial') else uuid.uuid4(),
        'form': form,
    }
    context = check_organization_context(request, context)
    return render(request, 'ampel.html', context=context)



@login_required
@required_person_cluster('aufgaben')
def aufgaben(request):

    erledigte_aufgaben = UserAufgaben.objects.filter(user=request.user, erledigt=True).order_by(
        'faellig')
    offene_aufgaben = UserAufgaben.objects.filter(user=request.user, erledigt=False,
                                                          pending=False).order_by('faellig')
    pending_aufgaben = UserAufgaben.objects.filter(user=request.user, erledigt=False,
                                                           pending=True).order_by('faellig')

    len_erledigt = erledigte_aufgaben.count()
    len_offen = offene_aufgaben.count()
    len_pending = pending_aufgaben.count()

    gesamt = len_erledigt + len_offen + len_pending

    # Create calendar events
    calendar_events = []
    
    # Add open tasks (blue)
    for aufgabe in offene_aufgaben:
        calendar_events.append({
            'title': aufgabe.aufgabe.name,
            'start': aufgabe.faellig.strftime('%Y-%m-%d') if aufgabe.faellig else '',
            'url': reverse('aufgaben_detail', args=[aufgabe.id]),
            'backgroundColor': '#0d6efd',
            'borderColor': '#0d6efd'
        })
    
    # Add pending tasks (yellow)
    for aufgabe in pending_aufgaben:
        calendar_events.append({
            'title': aufgabe.aufgabe.name,
            'start': aufgabe.faellig.strftime('%Y-%m-%d') if aufgabe.faellig else '',
            'url': reverse('aufgaben_detail', args=[aufgabe.id]),
            'backgroundColor': '#ffc107',
            'borderColor': '#ffc107',
            'textColor': '#000'
        })
    
    # Add completed tasks (green)
    for aufgabe in erledigte_aufgaben:
        calendar_events.append({
            'title': aufgabe.aufgabe.name,
            'start': aufgabe.faellig.strftime('%Y-%m-%d') if aufgabe.faellig else '',
            'url': reverse('aufgaben_detail', args=[aufgabe.id]),
            'backgroundColor': '#198754',
            'borderColor': '#198754'
        })

    context = {
        'aufgaben_offen': offene_aufgaben,
        'aufgaben_erledigt': erledigte_aufgaben,
        'aufgaben_pending': pending_aufgaben,
        'len_erledigt': len_erledigt,
        'erledigt_prozent': round(len_erledigt / gesamt * 100) if gesamt > 0 else 0,
        'len_pending': len_pending,
        'pending_prozent': round(len_pending / gesamt * 100) if gesamt > 0 else 0,
        'len_offen': len_offen,
        'offen_prozent': round(len_offen / gesamt * 100) if gesamt > 0 else 0,
        'show_confetti': request.GET.get('show_confetti') == 'true',
        'calendar_events': json.dumps(calendar_events)
    }
    context = check_organization_context(request, context)
    return render(request, 'aufgaben.html', context=context)


@login_required
@required_person_cluster('aufgaben')
def aufgabe(request, aufgabe_id):

    try:
        user_aufgabe = UserAufgaben.objects.get(id=aufgabe_id, org=request.user.org, user=request.user)
    except UserAufgaben.DoesNotExist:
        messages.error(request, 'Aufgabe nicht gefunden')
        return redirect('aufgaben')
    
    if request.method == 'POST':
        files = request.FILES.getlist('file')

        if user_aufgabe.aufgabe.mitupload:
            if files and len(files) > 1:
                # Create a zip file in memory
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, 'w') as zipf:
                    for i, file in enumerate(files):
                        file_suffix = os.path.splitext(file.name)[1]
                        # Create a unique filename within the zip
                        zip_filename = f"{user_aufgabe.user.username}-{user_aufgabe.aufgabe.name.replace(' ', '_')}-{datetime.now().strftime('%Y-%m-%d')}_{i}{file_suffix}"
                        # Add the file directly to the zip without creating temp files
                        zipf.writestr(zip_filename, file.read())

                # Reset buffer position to beginning
                zip_buffer.seek(0)
                
                # Create filename for the zip file
                file_name = f"{user_aufgabe.aufgabe.name.replace(' ', '_')}-{datetime.now().strftime('%Y-%m-%d')}.zip"
                
                # Save the zip file directly to the FileField using ContentFile
                # This properly handles the upload_to parameter and file storage
                user_aufgabe.file.save(file_name, ContentFile(zip_buffer.getvalue()), save=True)

            elif files:
                user_aufgabe.file = files[0]
                user_aufgabe.save()
        
        action = request.POST.get('action')
        if action == 'unpend':
            user_aufgabe.pending = False
            user_aufgabe.erledigt = False
            user_aufgabe.erledigt_am = None
        else:  # action == 'pending'
            if user_aufgabe.aufgabe.requires_submission:
                user_aufgabe.pending = True
                user_aufgabe.erledigt = False
            else:
                user_aufgabe.pending = False
                user_aufgabe.erledigt = True

            from ORG.tasks import send_aufgabe_erledigt_email_task
            send_aufgabe_erledigt_email_task.s(user_aufgabe.id).apply_async(countdown=10)

            user_aufgabe.erledigt_am = datetime.now()


        user_aufgabe.save()
        base_url = reverse('aufgaben')
        if action == 'pending':
            return redirect(f'{base_url}?show_confetti=true')
        return redirect(base_url)


    context = {
        'freiwilliger_aufgabe': user_aufgabe
    }
    context = check_organization_context(request, context)
    return render(request, 'aufgabe.html', context=context)


@login_required
def download_aufgabe_attachment(request, aufgabe_id):
    """Download attachment file from an Aufgabe2 object - accessible to all authenticated users"""
    try:
        aufgabe = Aufgabe2.objects.get(pk=aufgabe_id, org=request.user.org)
        if not aufgabe.attachment:
            return HttpResponse('Keine Datei gefunden')
        if not aufgabe.attachment.path:
            return HttpResponse('Datei nicht gefunden')
        if not os.path.exists(aufgabe.attachment.path):
            return HttpResponse('Datei nicht gefunden')
            
        response = HttpResponse(aufgabe.attachment.read(), content_type='application/octet-stream')
        response['Content-Disposition'] = f'attachment; filename="{aufgabe.attachment.name.replace(" ", "_")}"'

        return response
    except Aufgabe2.DoesNotExist:
        return HttpResponse('Nicht erlaubt')


@login_required
@required_person_cluster('posts')
def posts_overview(request):
    # Get the user's person_cluster
    user_person_cluster = request.user.person_cluster
    
    # For organization users, they can see all posts
    if user_person_cluster.view == 'O':
        posts = get_posts(request.user.org)
    else:
        # For regular users, only show posts assigned to their person_cluster
        # or posts that don't have any specific person_cluster assigned
        posts = get_posts(request.user.org, filter_person_cluster=user_person_cluster, filter_user=request.user)
    
    context = {
        'posts': posts
    }
    context = check_organization_context(request, context)
    return render(request, 'posts_overview.html', context=context)

@login_required
@required_person_cluster('posts')
def post_edit(request, post_id):
    post = Post2.objects.get(id=post_id)
    
    # Check permissions
    if request.user != post.user and request.user.role != 'A':
        messages.error(request, 'Sie haben keine Berechtigung, diesen Beitrag zu bearbeiten.')
        return redirect('post_detail', post_id=post_id)
    
    if request.method == 'POST':
        form = AddPostForm(request.POST, instance=post)
        if form.is_valid():
            # Save with commit=False to handle the post object
            post = form.save(commit=True)
            post.save()

            # Explicitly save the ManyToManyField
            form.save_m2m()
            if not post.person_cluster:
                post.person_cluster.set([request.user.person_cluster])
            messages.success(request, 'Beitrag erfolgreich aktualisiert.')
            return redirect('post_detail', post_id=post.id)
    else:
        # Prepare initial data for survey fields
        initial_data = {}
        if post.has_survey and hasattr(post, 'survey_question'):
            initial_data['survey_question'] = post.survey_question.question_text
            
            # Populate answer fields
            for i, answer in enumerate(post.survey_question.survey_answers.all()[:5], 1):
                initial_data[f'answer_{i}'] = answer.answer_text
                
        form = AddPostForm(instance=post, initial=initial_data)
    
    context = {
        'form': form,
        'post': post
    }
    context = check_organization_context(request, context)
    return render(request, 'post_add.html', context=context)



@login_required
@required_person_cluster('posts')
def post_add(request, post=None):
    if request.method == 'POST':
        form = AddPostForm(request.POST)
        if form.is_valid():
            # Save with commit=False to set user and org
            post = form.save(commit=False)
            post.user = request.user
            post.org = request.user.org
            post.save()

            # Save the survey question and answers
            form.save_answers()

            # Save person_cluster
            person_cluster = form.cleaned_data.get('person_cluster')
            if person_cluster:
                post.person_cluster.set(person_cluster)

            # Explicitly save the ManyToManyField after saving the post
            form.save_m2m()
            messages.success(request, 'Beitrag erfolgreich erstellt.')
            return redirect('posts_overview')
    elif post:
        form = AddPostForm(instance=post)
    else:
        form = AddPostForm()
    
    context = {
        'form': form,
        'post': post
    }
    context = check_organization_context(request, context)
    return render(request, 'post_add.html', context=context)

@login_required
@required_person_cluster('posts')
def post_detail(request, post_id):
    try:
        post = Post2.objects.get(id=post_id)
        
        # Check if user has permission to view this post based on person_cluster
        user_person_cluster = request.user.person_cluster
        if user_person_cluster.view != 'O' and post.person_cluster.exists():
            # Check if the user's cluster is in the post's allowed clusters
            if user_person_cluster not in post.person_cluster.all():
                messages.error(request, 'Sie haben keine Berechtigung, diesen Beitrag anzusehen.')
                return redirect('posts_overview')
        
        # Track if user has voted in this survey
        has_voted = False
        total_votes = 0
        
        if post.has_survey and hasattr(post, 'survey_question'):
            # Check if user has voted using the ManyToManyField
            answers = PostSurveyAnswer.objects.filter(question=post.survey_question)
            has_voted = False
            for answer in answers:
                total_votes += answer.votes.count()
                if request.user in answer.votes.all():
                    has_voted = answer

        context = {
            'post': post,
            'has_voted': has_voted,
            'total_votes': total_votes
        }

        context = check_organization_context(request, context)
        return render(request, 'post_detail.html', context=context)
    except Post2.DoesNotExist:
        messages.error(request, 'Beitrag nicht gefunden.')
        return redirect('posts_overview')
    except Exception as e:
        messages.error(request, f'Fehler: {e}')
        return redirect('posts_overview')

@login_required
@required_person_cluster('posts')
def post_delete(request, post_id):
    post = Post2.objects.get(id=post_id)
    
    # Check if user has permission to delete this post
    if request.user == post.user or request.user.role == 'A':
        post.delete()
    
    return redirect('posts_overview')

@login_required
@required_person_cluster('posts')
def post_vote(request, post_id):
    if request.method != 'POST':
        return redirect('post_detail', post_id=post_id)
    
    post = Post2.objects.get(id=post_id)
    
    # Check if post has a survey
    if not post.has_survey or not hasattr(post, 'survey_question'):
        messages.error(request, 'Diese Umfrage existiert nicht oder wurde entfernt.')
        return redirect('post_detail', post_id=post_id)
    
    # Process the vote
    answer_id = request.POST.get('answer_id')
    if answer_id:
        try:
            answer = PostSurveyAnswer.objects.get(id=answer_id, question=post.survey_question)
            if request.user in answer.votes.all():
                messages.info(request, 'Du hast bereits an dieser Umfrage teilgenommen.')
                return redirect('post_detail', post_id=post_id)
            
            # Add user to the votes ManyToManyField of this answer
            answer.votes.add(request.user)
            
        except PostSurveyAnswer.DoesNotExist:
            messages.error(request, 'Die gewählte Antwort existiert nicht.')
    else:
        messages.error(request, 'Bitte wählen Sie eine Antwort aus.')
    
    return redirect('post_detail', post_id=post_id)


@login_required
@required_role('OT')
def einsatzstellen_notiz(request, es_id=None):
    # Get all Einsatzstellen for the selector, grouped by land
    if request.user.role == 'T':
        from TEAM.views import _get_team_member
        team = _get_team_member(request)
        if team:
            einsatzstellen = Einsatzstelle2.objects.filter(org=request.user.org, land__in=team.land.all()).order_by('land__name', 'name')
        else:
            messages.error(request, 'Team nicht gefunden.')
            return redirect('index_home')
    else:
        einsatzstellen = Einsatzstelle2.objects.filter(org=request.user.org).order_by('land__name', 'name')
    
    # Get the selected Einsatzstelle
    einsatzstelle = None
    
    if request.GET.get('es_id'):
        return redirect('einsatzstellen_notiz', es_id=request.GET.get('es_id'))
    
    if es_id:
        try:
            if request.user.role == 'T':
                from TEAM.views import _get_team_member
                team = _get_team_member(request)
                if team:
                    einsatzstelle = Einsatzstelle2.objects.get(id=es_id, land__in=team.land.all())
                else:
                    messages.error(request, 'Team nicht gefunden.')
                    return redirect('index_home')
            else:
                einsatzstelle = Einsatzstelle2.objects.get(id=es_id, org=request.user.org)
        except Einsatzstelle2.DoesNotExist:
            messages.error(request, 'Einsatzstelle nicht gefunden.')
            return redirect('einsatzstellen_notiz')
    
    # Handle note deletion
    if request.method == 'POST' and 'delete_notiz_id' in request.POST:
        notiz_id = request.POST.get('delete_notiz_id')
        try:
            notiz = EinsatzstelleNotiz.objects.get(id=notiz_id, user=request.user)
            notiz.delete()
            messages.success(request, 'Notiz erfolgreich gelöscht.')
        except EinsatzstelleNotiz.DoesNotExist:
            messages.error(request, 'Notiz konnte nicht gelöscht werden.')
        return redirect('einsatzstellen_notiz', es_id=es_id)
    
    # Handle note pinning/unpinning
    if request.method == 'POST' and 'action' in request.POST and request.POST.get('action') in ['pin', 'unpin']:
        notiz_id = request.POST.get('notiz_id')
        try:
            notiz = EinsatzstelleNotiz.objects.get(id=notiz_id)
            notiz.pinned = request.POST.get('action') == 'pin'
            notiz.save()
        except EinsatzstelleNotiz.DoesNotExist:
            messages.error(request, 'Notiz konnte nicht aktualisiert werden.')
        return redirect('einsatzstellen_notiz', es_id=es_id)
    
    # Handle note editing
    if request.method == 'POST' and 'notiz_id' in request.POST and 'notiz' in request.POST:
        notiz_id = request.POST.get('notiz_id')
        try:
            notiz = EinsatzstelleNotiz.objects.get(id=notiz_id, user=request.user)
            notiz.notiz = request.POST.get('notiz')
            notiz.date = datetime.now()
            notiz.save()
            messages.success(request, 'Notiz erfolgreich aktualisiert.')
        except EinsatzstelleNotiz.DoesNotExist:
            messages.error(request, 'Notiz konnte nicht aktualisiert werden.')
        return redirect('einsatzstellen_notiz', es_id=es_id)
    
    # Handle new note creation
    if request.method == 'POST' and einsatzstelle:
        form = EinsatzstelleNotizForm(request.POST, einsatzstelle=einsatzstelle, request=request, org=request.user.org)
        if form.is_valid():
            form.save()
            messages.success(request, 'Notiz erfolgreich erstellt.')
            return redirect('einsatzstellen_notiz', es_id=es_id)
    else:
        form = EinsatzstelleNotizForm(einsatzstelle=einsatzstelle, request=request, org=request.user.org) if einsatzstelle else None
    
    # Get notes for the selected Einsatzstelle, ordered by pinned status and date
    notizen = EinsatzstelleNotiz.objects.filter(einsatzstelle=einsatzstelle).order_by('-pinned', '-date') if einsatzstelle else None

    context = {
        'form': form,
        'einsatzstelle': einsatzstelle,
        'einsatzstellen': einsatzstellen,
        'notizen': notizen
    }
    context = check_organization_context(request, context)
    return render(request, 'einsatzstellen_notiz.html', context=context)

def kalender_abbonement(request, token):
    try:
        # Load the token data without expiration checking
        custom_user = CustomUser.objects.get(calendar_token=token)
        print(custom_user)
        user = custom_user.user
        print(user)
        
        # Add calendar events
        if user.role == 'O':
            kalender_events = KalenderEvent.objects.filter(org=user.org)
        else:
            kalender_events = KalenderEvent.objects.filter(org=user.org).filter(user__in=[user])
            
        # Create iCal calendar
        cal = Calendar()
        cal.add('prodid', '-//Volunteer Solutions//Calendar//DE')
        cal.add('version', '2.0')
        cal.add('calscale', 'GREGORIAN')
        cal.add('method', 'PUBLISH')
        cal.add('name', f'Kalender von {user.first_name} {user.last_name}')
        cal.add('description', f'Kalender von {user.first_name} {user.last_name}')
        
        # Add user's tasks
        for user_aufgabe in UserAufgaben.objects.filter(user=user):
            ical_event = Event()
            ical_event.add('summary', user_aufgabe.aufgabe.name)
            # Convert date to datetime for iCal compatibility
            if user_aufgabe.faellig:
                # Convert date to datetime at midnight
                from datetime import datetime
                faellig_datetime = datetime.combine(user_aufgabe.faellig, datetime.min.time())
                ical_event.add('dtstart', faellig_datetime)
                ical_event.add('dtend', faellig_datetime)
            url = f"{request.scheme}://{request.get_host()}{reverse('aufgaben_detail', args=[user_aufgabe.id])}"
            ical_event.add('url', url)
            cal.add_component(ical_event)

        # Add calendar events
        for kalender_event in kalender_events:
            ical_event = Event()
            ical_event.add('summary', kalender_event.title)
            
            # Add location if available
            if kalender_event.location:
                ical_event.add('location', kalender_event.location)
            
            # Add description if available
            if kalender_event.description:
                ical_event.add('description', kalender_event.description)
            
            # Ensure proper timezone handling
            if kalender_event.start:
                start_dt = kalender_event.start.astimezone(timezone.get_current_timezone())
                ical_event.add('dtstart', start_dt)
            if kalender_event.end:
                end_dt = kalender_event.end.astimezone(timezone.get_current_timezone())
                ical_event.add('dtend', end_dt)
            url = f"{request.scheme}://{request.get_host()}{reverse('kalender_event', args=[kalender_event.id])}"
            ical_event.add('url', url)
            cal.add_component(ical_event)
            
        # Add birthdays
        from datetime import datetime as dt, time as dtime

        # If user is not authenticated, skip adding birthdays
        for custom_user in CustomUser.objects.filter(org=user.org):
            # Use getattr to avoid attribute errors if 'role' is missing
            user_role = custom_user.user.role
            current_user_role = user.role
            if user_role != current_user_role and current_user_role != 'O':
                continue

            if custom_user.geburtsdatum:
                birthday_date = custom_user.geburtsdatum
                for year_offset in range(dt.now().year - birthday_date.year + 10):
                    ical_event = Event()
                    ical_event.add('summary', f'Geburtstag von {getattr(custom_user.user, "first_name", "")} {getattr(custom_user.user, "last_name", "")}')
                    # Use date object for all-day events
                    current_birthday = birthday_date.replace(year=birthday_date.year + year_offset)
                    ical_event.add('dtstart', current_birthday)
                    ical_event['dtstart'].params['VALUE'] = 'DATE'  # Mark as all-day event
                    user_id = getattr(custom_user.user, 'id', None)
                    if user_id is not None:
                        url = f"{request.scheme}://{request.get_host()}{reverse('profil', args=[user_id])}"
                        ical_event.add('url', url)
                    cal.add_component(ical_event)

        # Check if this is a calendar app request
        is_calendar_app = (
            request.headers.get('Accept') == 'text/calendar' or 
            request.GET.get('format') == 'ical' or
            'calendar' in request.headers.get('User-Agent', '').lower()
        )

        response = HttpResponse(cal.to_ical(), content_type='text/calendar')
        
        if is_calendar_app:
            # For calendar apps, return as inline content
            response['Content-Disposition'] = f'inline; filename="kalender_{user.username}.ics"'
        else:
            # For direct downloads, trigger file download
            response['Content-Disposition'] = f'attachment; filename="kalender_{user.username}.ics"'
        
        return response

    except Exception as e:
        messages.error(request, f'Ungültiger Token.')
        print(e)
        return redirect('index_home')
    
@login_required
def settings_view(request):
    context = check_organization_context(request, {})
    return render(request, 'settings.html', context=context)

@login_required
def delete_account(request):
    #send mail to admin
    if request.method == 'POST':
        mail_addresses = settings.ADMINS
        for mail_address in mail_addresses:
            send_email_with_archive(
                subject='Konto-Löschung beantragt',
                message=f'Ein Benutzer hat die Löschung seines Kontos beantragt. {request.user.first_name} {request.user.last_name} ({request.user.email})',
                from_email=settings.SERVER_EMAIL,
                recipient_list=[mail_address[1]],
                html_message=f'Ein Benutzer hat die Löschung seines Kontos beantragt. {request.user.first_name} {request.user.last_name} ({request.user.email})',
                reply_to_list=[request.user.email]
            )
        messages.success(request, 'Konto-Löschung beantragt. Sie erhalten eine E-Mail, sobald Ihr Antrag bearbeitet wurde.')
        return redirect('settings')
    return redirect('settings')

@login_required
def export_data(request):
    """
    Export all user data including foreign key relationships as a JSON file.
    
    This is a wrapper function that uses the secure export utilities module.
    All security features are implemented in the export_utils module.
    """
    try:
        return export_user_data_securely(request.user)
    except ValueError as e:
        # Handle specific validation errors (rate limiting, permissions, etc.)
        messages.error(request, str(e))
        return redirect('settings')
    except Exception as e:
        # SECURITY: Generic error message to prevent information disclosure
        logger = logging.getLogger('security')
        logger.error(f'Data export failed for user {request.user.id} ({request.user.username}): {str(e)}')
        
        messages.error(request, 'Beim Export der Daten ist ein Fehler aufgetreten. Bitte versuchen Sie es später erneut.')
        return redirect('settings')


@login_required
@required_role('ET')
def list_bewerber(request):
    bewerber = Bewerber.objects.filter(org=request.user.org, accessible_by_team_member__in=[request.user])
    context = {
        'bewerber': bewerber
    }
    context = check_organization_context(request, context)
    return render(request, 'list_bewerber.html', context=context)


@login_required
@required_role('ET')
def bewerber_detail(request, bewerber_id):
    try:
        bewerber = Bewerber.objects.get(id=bewerber_id, org=request.user.org, accessible_by_team_member=request.user)
        bewerber_fragen = ApplicationAnswer.objects.filter(org=request.user.org, user=bewerber.user)
        bewerber_files = ApplicationAnswerFile.objects.filter(org=request.user.org, user=bewerber.user)
        context = {
            'bewerber': bewerber,
            'bewerber_fragen': bewerber_fragen,
            'bewerber_files': bewerber_files
        }
        context = check_organization_context(request, context)
        return render(request, 'bewerber_detail.html', context=context)
    except Exception as e:
        messages.error(request, f'Fehler: {e}')
        return redirect('index_home')

@login_required
@required_role('O')
def bewerber_kommentar(request, bewerber_id):
    try:
        bewerber = Bewerber.objects.get(id=bewerber_id, org=request.user.org)
        
        if request.method == 'POST':
            form = BewerberKommentarForm(request.POST)
            if form.is_valid():
                kommentar = form.save(commit=False)
                kommentar.bewerber = bewerber
                kommentar.org = request.user.org
                kommentar.user = request.user
                kommentar.save()
                return redirect('bewerber_kommentar', bewerber_id=bewerber.id)
        else:
            form = BewerberKommentarForm()
        
        # Get all comments for this bewerber
        all_comments = BewerberKommentar.objects.filter(
            bewerber=bewerber,
            org=request.user.org
        ).select_related('user').order_by('-date_created')
        
        context = {
            'bewerber': bewerber,
            'form': form,
            'all_comments': all_comments,
        }
        
        return render(request, 'bewerber_kommentar.html', context)
        
    except Exception as e:
        messages.error(request, f'Fehler: {e}')
        return redirect('index_home')
    

@login_required
@required_role('BOTE')
def bw_application_file_answer_download(request, file_answer_id):
    try:
        if request.user.customuser.person_cluster.view == 'B':
            file_answer = ApplicationAnswerFile.objects.get(id=file_answer_id, user=request.user)
        else:
            file_answer = ApplicationAnswerFile.objects.get(id=file_answer_id, file_question__org=request.user.org)
            if request.user.customuser.person_cluster.view in 'TE':
                try:
                    file_answer_user = file_answer.user
                    file_answer_bewerber = Bewerber.objects.get(user=file_answer_user, org=request.user.org)
                    if not file_answer_bewerber.accessible_by_team_member.filter(id=request.user.id).exists():
                        messages.error(request, 'Sie haben keine Berechtigung, diese Datei herunterzuladen')
                        return redirect('index_home')
                except Exception as e:
                    messages.error(request, 'Datei nicht gefunden')
                    return redirect('index_home')
                
    except ApplicationAnswerFile.DoesNotExist:
        messages.error(request, 'Datei nicht gefunden')
        return redirect('index_home')
    
    if file_answer.file and os.path.exists(file_answer.file.path):
        response = FileResponse(file_answer.file)
        response['Content-Disposition'] = f'attachment; filename="{file_answer.file.name}"'
        return response
    else:
        messages.error(request, 'Datei nicht gefunden')
        return redirect('index_home')


# ============================================================================
# Country and Placement Location Information Views (Team & Ehemalige)
# ============================================================================

def _get_member_and_countries(request):
    """
    Get member (Team or Ehemalige) and their assigned countries.
    Returns tuple of (member, assigned_countries, base_template)
    """
    from TEAM.models import Team
    from Ehemalige.models import Ehemalige
    
    user_view = request.user.customuser.person_cluster.view
    
    if user_view == 'T':
        # Team member
        member = Team.objects.filter(user=request.user).first()
        if member:
            return member, member.land.all(), 'baseTeam.html'
    elif user_view == 'E':
        # Ehemalige member
        member = Ehemalige.objects.filter(user=request.user).first()
        if member:
            return member, member.land.all(), 'baseEhemalige.html'
        
    return None, None, 'base.html'


@login_required
@required_role('TE')
def laender_info(request):
    """View for Team and Ehemalige members to view their assigned countries' information."""
    member, assigned_countries, base_template = _get_member_and_countries(request)
    
    if not member:
        messages.warning(request, 'Ihrem Konto sind keine Einsatzländer zugeordnet. Bitte kontaktieren Sie den Administrator.')
        return redirect('index_home')
    
    # Get assigned countries
    laender = assigned_countries.order_by('name')
    
    # Check if there are any countries assigned
    if not laender.exists():
        messages.info(request, 'Ihrem Konto sind derzeit keine Einsatzländer zugeordnet.')
    
    # Get pending change requests for this user's countries
    pending_requests_by_land = {}
    if laender.exists():
        pending_requests = ChangeRequest.objects.filter(
            org=request.user.org,
            requested_by=request.user,
            status='pending',
            change_type='einsatzland',
            object_id__in=laender.values_list('id', flat=True)
        ).select_related('requested_by')
        
        for req in pending_requests:
            pending_requests_by_land[req.object_id] = req
    
    context = {
        'laender': laender,
        'pending_requests_by_land': pending_requests_by_land,
        'base_template': base_template,
        'member': member
    }
    
    return render(request, 'laender_info.html', context)


@login_required
@required_role('TE')
def einsatzstellen_info(request):
    """View for Team and Ehemalige members to view their assigned placement locations."""
    member, assigned_countries, base_template = _get_member_and_countries(request)
    
    if not member:
        messages.warning(request, 'Ihrem Konto sind keine Einsatzstellen zugeordnet. Bitte kontaktieren Sie den Administrator.')
        return redirect('index_home')
    
    # Get placement locations for assigned countries
    einsatzstellen = Einsatzstelle2.objects.filter(
        org=request.user.org,
        land__in=assigned_countries
    ).select_related('land').order_by('land__name', 'name')
    
    # Check if there are any placement locations
    if not einsatzstellen.exists():
        messages.info(request, 'Es wurden keine Einsatzstellen in Ihren zugewiesenen Ländern gefunden.')
    
    # Get pending change requests for this user's einsatzstellen
    pending_requests_by_stelle = {}
    if einsatzstellen.exists():
        pending_requests = ChangeRequest.objects.filter(
            org=request.user.org,
            requested_by=request.user,
            status='pending',
            change_type='einsatzstelle',
            object_id__in=einsatzstellen.values_list('id', flat=True)
        ).select_related('requested_by')
        
        for req in pending_requests:
            pending_requests_by_stelle[req.object_id] = req
    
    context = {
        'einsatzstellen': einsatzstellen,
        'pending_requests_by_stelle': pending_requests_by_stelle,
        'base_template': base_template,
        'member': member
    }
    
    return render(request, 'einsatzstellen_info.html', context)
