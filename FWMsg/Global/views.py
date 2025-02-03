from datetime import datetime
import mimetypes
import os
import subprocess
from django.contrib import messages
from django.contrib.auth import logout
from django.http import HttpResponseRedirect, HttpResponse, Http404, HttpResponseNotAllowed, HttpResponseNotFound

from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.shortcuts import redirect, render

from django.contrib.auth.models import User
from FW.forms import BilderForm, BilderGalleryForm, ProfilUserForm
from FW.models import Ampel, Bilder, BilderGallery, CustomUser, Freiwilliger, ProfilUser
from ORG.models import Dokument, Ordner

from ORG.views import base_template

from FW.tasks import send_aufgaben_email_task

from FWMsg.celery import send_email_aufgaben_daily

from FWMsg.decorators import required_role

from .forms import FeedbackForm

def send_aufgaben_email(request):
    print('send_aufgaben_email')
    send_email_aufgaben_daily.delay()
    return HttpResponse({"success": True, "message": "Email sent"}, content_type="application/json")

def datenschutz(request):
    return render(request, 'datenschutz.html')


def checkForOrg(request, context):
    if not request.user.is_authenticated or not hasattr(request.user, 'customuser'):
        return context
    if request.user.customuser.role == 'O':
        context['extends_base'] = base_template
        context['is_org'] = True
    return context

@login_required
@required_role('')
def serve_logo(request, image_name):
    # Define the path to the image directory
    image_path = os.path.join(settings.LOGOS_PATH, image_name)

    print('image_path:', image_path)

    # Check if the file exists
    if not os.path.exists(image_path):
        return HttpResponseNotFound('Bild nicht gefunden')

    # Open the image file in binary mode
    with open(image_path, 'rb') as img_file:
        # Determine the content type (you might want to use a library to detect this)
        content_type = 'image/jpeg'  # Change this if your images are in different formats
        response = HttpResponse(img_file.read(), content_type=content_type)
        response['Content-Disposition'] = f'inline; filename="{image_name}"'

    return response

@login_required
@required_role('')
def serve_bilder(request, image_id):
    # Define the path to the image directory
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
    # Define the path to the image directory
    bild_exists = BilderGallery.objects.filter(id=image_id).exists()
    if not bild_exists:
        return HttpResponseNotFound('Bild nicht gefunden')

    bild = BilderGallery.objects.get(id=image_id)

    if not bild.org == request.user.org:
        return HttpResponseNotAllowed('Nicht erlaubt')

    if not bild.small_image:
        return serve_bilder(request, image_id)

    return get_bild(bild.small_image.path, bild.bilder.titel)


def get_mimetype(doc_path):
    mime_type, _ = mimetypes.guess_type(doc_path)
    return mime_type



@login_required
@required_role('')
def serve_dokument(request, dokument_id):
    img = request.GET.get('img', None)
    download = request.GET.get('download', None)
    # Define the path to the image directory
    dokument_exists = Dokument.objects.filter(id=dokument_id).exists()
    if not dokument_exists:
        return HttpResponseNotFound('Dokument nicht gefunden')

    dokument = Dokument.objects.get(id=dokument_id)
    if not dokument.org == request.user.org:
        return HttpResponseNotAllowed('Nicht erlaubt')

    doc_path = dokument.dokument.path

    if not os.path.exists(doc_path):
        return HttpResponseNotFound('Dokument nicht gefunden')

    mimetype = get_mimetype(doc_path)
    if mimetype and mimetype.startswith('image') and not download:
        return get_bild(doc_path, dokument.dokument.name)

    if img and not download:
        img_path = dokument.get_preview_image()
        print('img_path:', img_path)
        if img_path:
            return get_bild(img_path, img_path.split('/')[-1])

    with open(doc_path, 'rb') as file:
        response = HttpResponse(file.read(), content_type=mimetype or 'application/octet-stream')
        response['Content-Disposition'] = f'attachment; filename="{dokument.dokument.name}"'
        return response

def get_bilder(request, filter_user=None):
    bilder = Bilder.objects.filter(org=request.user.org)
    if filter_user:
        bilder = bilder.filter(user=filter_user)
    gallery_images = {}
    for bild in bilder:
        gallery_images[bild] = BilderGallery.objects.filter(bilder=bild)
    return gallery_images

@login_required
def bilder(request):
    gallery_images = get_bilder(request)

    context={'gallery_images': gallery_images}

    context = checkForOrg(request, context)

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

    context = checkForOrg(request, context)

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

    context = checkForOrg(request, context)

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


def get_bild(image_path, image_name):
    print('image_path:', image_path)
    if not os.path.exists(image_path):
        raise Http404("Image does not exist")

    # Open the image file in binary mode
    with open(image_path, 'rb') as img_file:
        # Determine the content type (you might want to use a library to detect this)
        content_type = 'image/jpeg'  # Change this if your images are in different formats
        response = HttpResponse(img_file.read(), content_type=content_type)
        response['Content-Disposition'] = f'inline; filename="{image_name}"'
        return response


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
    gallery_images = get_bilder(request, user)

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

    context = checkForOrg(request, context)

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
    context = checkForOrg(request, context)
    return render(request, 'feedback.html', context=context)