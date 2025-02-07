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
from datetime import datetime
import json
import mimetypes
import os
import subprocess

# Django imports
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.conf import settings
from django.http import (
    HttpResponseRedirect, 
    HttpResponse, 
    Http404, 
    HttpResponseNotAllowed, 
    HttpResponseNotFound
)
from django.shortcuts import redirect, render
from django.urls import reverse

# Local application imports
from FW.forms import BilderForm, BilderGalleryForm, ProfilUserForm
from FW.models import (
    Ampel, 
    Bilder, 
    BilderGallery, 
    Freiwilliger, 
    ProfilUser, 
    FreiwilligerAufgaben
)
from Global.models import KalenderEvent, CustomUser
from ORG.models import Dokument, Ordner, Organisation
from ORG.views import base_template
from FWMsg.celery import send_email_aufgaben_daily
from FWMsg.decorators import required_role
from .forms import FeedbackForm

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

def get_bilder(org, filter_user=None):
    """
    Retrieve gallery images, optionally filtered by user.
    
    Args:
        org: The organization object
        filter_user (User, optional): User to filter images by. Defaults to None.
        
    Returns:
        list: List of dictionaries containing gallery images and their metadata
    """
    bilder = Bilder.objects.filter(org=org).order_by('-date_created')
    if filter_user:
        bilder = bilder.filter(user=filter_user)

    gallery_images = []
    for bild in bilder:
        gallery_images.append({
            bild: BilderGallery.objects.filter(bilder=bild)
        })
    return gallery_images

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
    if not request.user.is_authenticated or not hasattr(request.user, 'customuser'):
        return context

    # Add organization-specific template settings if user is an organization
    if request.user.customuser.role == 'O':
        context.update({
            'extends_base': base_template,
            'is_org': True
        })

    return context

# Basic Views
def datenschutz(request):
    """Render the privacy policy page."""
    return render(request, 'datenschutz.html')

@login_required
@required_role('')
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

    org_exists = Organisation.objects.filter(id=org_id).exists()
    if not org_exists:
        return HttpResponseNotFound('Organisation nicht gefunden')

    org = Organisation.objects.get(id=org_id)

    if not request.user.org == org:
        return HttpResponseNotAllowed('Nicht erlaubt')
    
    if not org.logo:
        return HttpResponseNotFound('Logo nicht gefunden')

    image_path = org.logo.path

    if not os.path.exists(image_path):
        return HttpResponseNotFound('Bild nicht gefunden')

    with open(image_path, 'rb') as img_file:
        content_type = 'image/jpeg'
        response = HttpResponse(img_file.read(), content_type=content_type)
        response['Content-Disposition'] = f'inline; filename="{org.logo.name}"'

    return response

@login_required
@required_role('')
def serve_bilder(request, image_id):
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
    bild_exists = BilderGallery.objects.filter(id=image_id).exists()
    if not bild_exists:
        return HttpResponseNotFound('Bild nicht gefunden')

    bild = BilderGallery.objects.get(id=image_id)
    if not bild.org == request.user.org:
        return HttpResponseNotAllowed('Nicht erlaubt')
    
    return get_bild(bild.image.path, bild.bilder.titel)

@login_required
@required_role('')
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
    bild_exists = BilderGallery.objects.filter(id=image_id).exists()
    if not bild_exists:
        return HttpResponseNotFound('Bild nicht gefunden')

    bild = BilderGallery.objects.get(id=image_id)
    if not bild.org == request.user.org:
        return HttpResponseNotAllowed('Nicht erlaubt')

    if not bild.small_image:
        return serve_bilder(request, image_id)

    return get_bild(bild.small_image.path, bild.bilder.titel)

@login_required
@required_role('')
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

    dokument_exists = Dokument.objects.filter(id=dokument_id).exists()
    if not dokument_exists:
        return HttpResponseNotFound('Dokument nicht gefunden')

    dokument = Dokument.objects.get(id=dokument_id)
    if not dokument.org == request.user.org:
        return HttpResponseNotAllowed('Nicht erlaubt')

    doc_path = dokument.dokument.path
    if not os.path.exists(doc_path):
        return HttpResponseNotFound('Dokument nicht gefunden')

    # Handle image documents
    mimetype = get_mimetype(doc_path)
    if mimetype and mimetype.startswith('image') and not download:
        return get_bild(doc_path, dokument.dokument.name)

    # Handle preview images
    if img and not download:
        img_path = dokument.get_preview_image()
        if img_path:
            return get_bild(img_path, img_path.split('/')[-1])

    # Serve document as download
    with open(doc_path, 'rb') as file:
        response = HttpResponse(file.read(), content_type=mimetype or 'application/octet-stream')
        response['Content-Disposition'] = f'attachment; filename="{dokument.dokument.name}"'
        return response

@login_required
@required_role('')
def bilder(request):
    gallery_images = get_bilder(request.user.org)

    context={'gallery_images': gallery_images}

    context = check_organization_context(request, context)

    return render(request, 'bilder.html', context=context)

@login_required
@required_role('')
def bild(request):
    form_errors = None

    if request.POST:
        bilder_form = BilderForm(request.POST)
        images = request.FILES.getlist('image')

        if bilder_form.is_valid() and len(images) > 0:
            bilder_form_data = bilder_form.cleaned_data

            bilder, created = Bilder.objects.get_or_create(
                org=request.user.org,
                user=request.user,
                titel=bilder_form_data['titel'],
                beschreibung=bilder_form_data['beschreibung'],
                defaults={'date_created': datetime.now(), 'date_updated': datetime.now()}
            )

            if not created:
                bilder.date_updated = datetime.now()
                bilder.save()

            # Save each image with a reference to the product
            for image in images:
                try:
                    BilderGallery.objects.create(
                        org=request.user.org,
                        bilder=bilder,
                        image=image
                    )
                except Exception as e:
                    messages.error(request, f'Error saving image: {str(e)}')
                    continue

            return redirect('bilder')
        else:
            form_errors = bilder_form.errors

    bilder_form = BilderForm()
    bilder_gallery_form = BilderGalleryForm()
    
    context = {
        'bilder_form': bilder_form,
        'bilder_gallery_form': bilder_gallery_form,
        'form_errors': form_errors
    }

    context = check_organization_context(request, context)

    return render(request, 'bild.html', context=context)

@login_required
@required_role('')
def remove_bild(request):
    gallery_image_id = request.GET.get('galleryImageId', None)
    bild_id = request.GET.get('bildId', None)

    if not gallery_image_id and not bild_id:
        messages.error(request, 'Kein Bild gefunden')
        return redirect('profil')

    try:
        gallery_image_exists = BilderGallery.objects.filter(id=gallery_image_id).exists()
        if not gallery_image_exists:
            messages.error(request, 'Bild nicht gefunden')
            return redirect('profil')
        
        gallery_image = BilderGallery.objects.get(id=gallery_image_id)
        
        if gallery_image.bilder.user != request.user:
            messages.error(request, 'Nicht erlaubt')
            return redirect('profil')

        # Check if this is the last image in the gallery
        related_gallery_images = BilderGallery.objects.filter(bilder=gallery_image.bilder)
        if related_gallery_images.count() == 1:
            # Delete the parent Bilder object if this is the last image
            gallery_image.bilder.delete()
        else:
            # Otherwise just delete this specific image
            gallery_image.delete()

        messages.success(request, 'Bild erfolgreich gelöscht')
        
    except BilderGallery.DoesNotExist:
        messages.error(request, 'Bild nicht gefunden')

    return redirect('profil')

@login_required
@required_role('')
def remove_bild_all(request):
    bild_id = request.GET.get('bild_id', None)
    if not bild_id:
        messages.error(request, 'Kein Bild gefunden')
        return redirect('profil')
    
    bild_exists = Bilder.objects.filter(id=bild_id).exists()
    if not bild_exists:
        messages.error(request, 'Bild nicht gefunden')
        return redirect('profil')
    
    bild = Bilder.objects.get(id=bild_id)
    if bild.user != request.user:
        messages.error(request, 'Nicht erlaubt')
        return redirect('profil')
    
    bilder_gallery = BilderGallery.objects.filter(bilder=bild)
    for bild_gallery in bilder_gallery:
        bild_gallery.delete()
    bild.delete()
    messages.success(request, 'Alle Bilder erfolgreich gelöscht')
    return redirect('profil')

@login_required
@required_role('')
def dokumente(request, ordner_id=None):
    ordners = Ordner.objects.filter(org=request.user.org).order_by('ordner_name')

    folder_structure = []

    for ordner in ordners:
        folder_structure.append({
            'ordner': ordner,
            'dokumente': Dokument.objects.filter(org=request.user.org, ordner=ordner).order_by('-date_created')
        })

    context = {
        'ordners': ordners,
        'folder_structure': folder_structure,
        'ordner_id': ordner_id
    }

    context = check_organization_context(request, context)

    return render(request, 'dokumente.html', context=context)

@login_required
@required_role('')
def add_dokument(request):
    if request.method == 'POST':
        dokument_id = request.POST.get('dokument_id')
        titel = request.POST.get('titel')
        beschreibung = request.POST.get('beschreibung')
        link = request.POST.get('link')
        fw_darf_bearbeiten = request.POST.get('fw_darf_bearbeiten') == 'on'

        file = request.FILES.get('dokument')

        if dokument_id and Dokument.objects.filter(id=dokument_id).exists():
            dokument = Dokument.objects.get(id=dokument_id)
            if dokument.org != request.user.org:
                messages.error(request, 'Nicht erlaubt')
                return redirect('dokumente')

            if file:
                dokument.dokument = file

            dokument.titel = titel
            dokument.beschreibung = beschreibung
            dokument.link = link
            dokument.fw_darf_bearbeiten = fw_darf_bearbeiten
            dokument.save()
        else:
            ordner = Ordner.objects.get(id=request.POST.get('ordner'))
            dokument = Dokument.objects.create(
                org=request.user.org,
                ordner=ordner,
                titel=titel,
                beschreibung=beschreibung,
                dokument=file,
                link=link,
                fw_darf_bearbeiten=fw_darf_bearbeiten,
                date_created=datetime.now()
            )

    return redirect('dokumente', ordner_id=dokument.ordner.id)

@login_required
@required_role('')
def add_ordner(request):
    if request.method == 'POST':
        ordner_id = request.POST.get('ordner_id')
        ordner_name = request.POST.get('ordner_name')
        if ordner_id and Ordner.objects.filter(id=ordner_id).exists():
            ordner = Ordner.objects.get(id=ordner_id)
            if ordner.org != request.user.org:
                messages.error(request, 'Nicht erlaubt')
                return redirect('dokumente')
            ordner.ordner_name = ordner_name
            ordner.save()
        else:
            ordner = Ordner.objects.create(org=request.user.org, ordner_name=ordner_name)

    return redirect('dokumente', ordner_id=ordner.id)

@login_required
@required_role('')
def remove_dokument(request):
    if request.method == 'POST':
        dokument_id = request.POST.get('dokument_id')
        try:
            dokument = Dokument.objects.get(id=dokument_id, org=request.user.org)
            if dokument.fw_darf_bearbeiten or request.user.customuser.role == 'O':
                dokument.delete()
            else:
                messages.error(request, 'Dokument kann nicht gelöscht werden, da es von einem FW bearbeitet wird.')
        except Dokument.DoesNotExist:
            pass

    return redirect('dokumente')

@login_required
@required_role('')
def remove_ordner(request):
    if request.method == 'POST':
        ordner_id = request.POST.get('ordner_id')
        try:
            ordner = Ordner.objects.get(id=ordner_id, org=request.user.org)
            # Only delete if folder is empty
            if not Dokument.objects.filter(ordner=ordner).exists():
                ordner.delete()
                messages.success(request, 'Ordner wurde gelöscht.')
            else:
                messages.error(request, f'Ordner {ordner.ordner_name} konnte nicht gelöscht werden, da er nicht leer ist.')
        except Ordner.DoesNotExist:
            pass

    return redirect('dokumente')

@login_required
@required_role('')
def update_profil_picture(request):
    if request.method == 'POST' and request.FILES.get('profil_picture'):
        try:
            custom_user = request.user.customuser
            # Delete old profil picture if it exists
            if custom_user.profil_picture:
                custom_user.profil_picture.delete()
            
            custom_user.profil_picture = request.FILES['profil_picture']
            custom_user.save()
            messages.success(request, 'Profilbild wurde erfolgreich aktualisiert.')
        except Exception as e:
            messages.error(request, f'Fehler beim Aktualisieren des Profilbildes: {str(e)}')
    
    return redirect('profil')

@login_required
@required_role('')
def serve_profil_picture(request, user_id):
    requested_user = User.objects.get(id=user_id)

    if not requested_user.customuser.org == request.user.org:
        return 'not allowed'
    
    if not requested_user.customuser.profil_picture:
        return get_bild(os.path.join(settings.STATIC_ROOT, 'img/default_img.png'), 'default_img.png')

    return get_bild(requested_user.customuser.profil_picture.path, requested_user.customuser.profil_picture.name)

@login_required
@required_role('')
def view_profil(request, user_id=None):
    this_user = False
    if not user_id or user_id == request.user.id:
        user_id = request.user.id
        this_user = True

    user_exists = User.objects.filter(id=user_id).exists()
    if not user_exists:
        messages.error(request, 'Nicht gefunden')
        return redirect('profil')
    
    user = User.objects.get(id=user_id)

    custom_user_exists = CustomUser.objects.filter(user=user).exists()
    if not custom_user_exists:
        messages.error(request, 'Nicht gefunden')
        return redirect('profil')
    
    custom_user = CustomUser.objects.get(user=user)
    if not custom_user.org == request.user.org:
        messages.error(request, 'Nicht erlaubt')
        return redirect('profil')

    if request.method == 'POST':
        profil_user_form = ProfilUserForm(request.POST)
        if profil_user_form.is_valid():
            profil_user = profil_user_form.save(commit=False)
            profil_user.user = request.user
            profil_user.org = request.user.org
            profil_user.save()
            return redirect('profil')

    profil_users = ProfilUser.objects.filter(user=user)
    gallery_images = get_bilder(request.user.org, user)

    ampel_of_user = None
    if this_user:
        ampel_of_user = Ampel.objects.filter(freiwilliger__user=user).order_by('-date').first()

    profil_user_form = ProfilUserForm()
    if Freiwilliger.objects.filter(user=user).exists():
        freiwilliger = Freiwilliger.objects.get(user=user)
    else:
        freiwilliger = None

    context = {
        'freiwilliger': freiwilliger,
        'user': user,
        'profil_users': profil_users,
        'profil_user_form': profil_user_form,
        'this_user': this_user,
        'ampel_of_user': ampel_of_user,
        'gallery_images': gallery_images
    }

    context = check_organization_context(request, context)

    return render(request, 'profil.html', context=context)

@login_required
@required_role('')
def remove_profil_attribut(request, profil_id):
    profil_user = ProfilUser.objects.get(id=profil_id)
    if profil_user.user == request.user:
        profil_user.delete()
    return redirect('profil')

@login_required
@required_role('')
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
@required_role('')
def kalender(request):
    calendar_events = []
    
    for freiwilliger_aufgabe in FreiwilligerAufgaben.objects.filter(freiwilliger__user=request.user):
        color = '#dc3545'  # Bootstrap danger color to match the theme
        if freiwilliger_aufgabe.erledigt:
            color = '#198754'  # Bootstrap success color
        elif freiwilliger_aufgabe.pending:
            color = '#ffc107'  # Bootstrap warning color
        elif freiwilliger_aufgabe.faellig and freiwilliger_aufgabe.faellig > datetime.now().date():
            color = '#0d6efd'  # Bootstrap primary color

        calendar_events.append({
            'title': freiwilliger_aufgabe.aufgabe.name,
            'start': freiwilliger_aufgabe.faellig.strftime('%Y-%m-%d') if freiwilliger_aufgabe.faellig else '',
            'url': reverse('aufgaben_detail', args=[freiwilliger_aufgabe.id]),
            'backgroundColor': color,
            'borderColor': color,
            'textColor': '#000'
        })

    birthday_events = Freiwilliger.objects.filter(geburtsdatum__isnull=False)
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
        
    kalender_events = KalenderEvent.objects.filter(org=request.user.org).filter(user__in=[request.user])
    for kalender_event in kalender_events:
        calendar_events.append({
            'title': kalender_event.title,
            'start': kalender_event.start.strftime('%Y-%m-%d %H:%M') if kalender_event.start else '',
            'end': kalender_event.end.strftime('%Y-%m-%d %H:%M') if kalender_event.end else '',
            'url': kalender_event.description,
            'backgroundColor': '#000',
            'borderColor': '#000',
            'textColor': '#fff'
        })

    context = {
        'calendar_events': json.dumps(calendar_events)
    }
    context = check_organization_context(request, context)
    return render(request, 'kalender.html', context=context)