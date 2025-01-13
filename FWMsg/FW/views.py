from datetime import datetime
import mimetypes
import os
import subprocess

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.db.models import Count
from django.http import HttpResponse, Http404
from django.shortcuts import render, redirect
from PIL import Image
import io
from django.conf import settings
from functools import wraps

from .forms import BilderForm, BilderGalleryForm, ProfilUserForm
from .models import (
    Freiwilliger, Aufgabe, FreiwilligerAufgabenprofil, 
    FreiwilligerAufgaben, Post, Bilder, CustomUser,
    BilderGallery, Ampel, ProfilUser
)
from ORG.models import Dokument, Ordner


@login_required
def home(request):
    """Dashboard view showing tasks, images and posts."""
    # Get task statistics
    task_queryset = FreiwilligerAufgaben.objects.filter(freiwilliger__user=request.user)
    
    erledigte_aufgaben = task_queryset.filter(erledigt=True).order_by('faellig')
    offene_aufgaben = task_queryset.filter(erledigt=False, pending=False).order_by('faellig')
    pending_aufgaben = task_queryset.filter(erledigt=False, pending=True).order_by('faellig')

    len_erledigt = erledigte_aufgaben.count()
    len_offen = offene_aufgaben.count() 
    len_pending = pending_aufgaben.count()
    gesamt = len_erledigt + len_offen + len_pending

    # Calculate percentages safely
    def safe_percentage(part, total):
        return round(part / total * 100) if total > 0 else 0

    freiwilliger_aufgaben = {
        'erledigt': erledigte_aufgaben,
        'erledigt_prozent': safe_percentage(len_erledigt, gesamt),
        'pending': pending_aufgaben,
        'pending_prozent': safe_percentage(len_pending, gesamt),
        'offen': offene_aufgaben,
        'offen_prozent': safe_percentage(len_offen, gesamt),
    }

    # Get recent images
    bilder = Bilder.objects.filter(org=request.user.org).order_by('-date_created')
    bilder_data = [
        {
            'bilder': bilder_obj,
            'images': BilderGallery.objects.filter(bilder=bilder_obj)
        }
        for bilder_obj in bilder[:2]
    ]

    context = {
        'aufgaben': freiwilliger_aufgaben,
        'bilder': bilder_data,
        'posts': Post.objects.all().order_by('date')[:3],
    }

    return render(request, 'home.html', context=context)


@login_required
def profil(request):
    profil_users = ProfilUser.objects.filter(user=request.user)
    context = {
        'profil_users': profil_users
    }
    return render(request, 'profil.html', context=context)


@login_required
def remove_profil(request, profil_id):
    profil_user = ProfilUser.objects.get(id=profil_id)
    if profil_user.user == request.user:
        profil_user.delete()
    return redirect('profil')


@login_required
def view_profil(request, user_id=None):
    this_user = False
    if not user_id or user_id == request.user.id:
        user_id = request.user.id
        this_user = True
    user = User.objects.get(id=user_id)

    if not CustomUser.objects.filter(user=user).exists() or not CustomUser.objects.get(user=user).org == request.user.org:
        messages.error(request, 'Nicht erlaubt')
        return redirect('fwhome')

    if request.method == 'POST':
        profil_user_form = ProfilUserForm(request.POST)
        if profil_user_form.is_valid():
            profil_user = profil_user_form.save(commit=False)
            profil_user.user = user
            profil_user.save()
            return redirect('profil')

    profil_users = ProfilUser.objects.filter(user=user)
    bilder_of_user = Bilder.objects.filter(user=user)
    bilder_gallery_of_user = BilderGallery.objects.filter(bilder__in=bilder_of_user).order_by('-bilder__date_created')
    print(bilder_gallery_of_user)

    ampel_of_user = None
    if this_user:
        ampel_of_user = Ampel.objects.filter(freiwilliger__user=user).order_by('-date').first()


    profil_user_form = ProfilUserForm()
    freiwilliger = Freiwilliger.objects.get(user=user)

    context = {
        'freiwilliger': freiwilliger,
        'profil_users': profil_users,
        'profil_user_form': profil_user_form,
        'this_user': this_user,
        'bilder_gallery_of_user': bilder_gallery_of_user,
        'ampel_of_user': ampel_of_user
    }
    return render(request, 'profil.html', context=context)


@login_required
def ampel(request):
    ampel = request.GET.get('ampel', None)
    if ampel and ampel.upper() in ['R', 'G', 'Y']:
        ampel = ampel.upper()
        comment = request.GET.get('comment', None)
        freiwilliger = Freiwilliger.objects.get(user=request.user)
        ampel_object = Ampel.objects.create(
            freiwilliger=freiwilliger, 
            status=ampel, 
            org=request.user.org,
            comment=comment
        )
        ampel_object.save()

        msg_text = 'Ampel erfolgreich auf ' + (
            'Grün' if ampel == 'G' else 'Rot' if ampel == 'R' else 'Gelb' if ampel == 'Y' else 'error') + ' gesetzt'

        messages.success(request, msg_text)
        return redirect('fwhome')

    last_ampel = Ampel.objects.filter(freiwilliger__user=request.user).order_by('-date').first()

    return render(request, 'ampel.html', context={'last_ampel': last_ampel})



@login_required
def aufgaben(request):
    erledigte_aufgaben = FreiwilligerAufgaben.objects.filter(freiwilliger__user=request.user, erledigt=True).order_by(
        'faellig')
    offene_aufgaben = FreiwilligerAufgaben.objects.filter(freiwilliger__user=request.user, erledigt=False,
                                                          pending=False).order_by('faellig')
    pending_aufgaben = FreiwilligerAufgaben.objects.filter(freiwilliger__user=request.user, erledigt=False,
                                                           pending=True).order_by('faellig')

    len_erledigt = erledigte_aufgaben.count()
    len_offen = offene_aufgaben.count()
    len_pending = pending_aufgaben.count()

    gesamt = len_erledigt + len_offen + len_pending

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
    }
    return render(request, 'aufgaben.html', context=context)


@login_required
def aufgabe(request, aufgabe_id):
    if request.method == 'POST':
        requested_aufgabe = Aufgabe.objects.get(id=aufgabe_id)
        freiwilliger_aufgaben = \
            FreiwilligerAufgaben.objects.filter(aufgabe=requested_aufgabe, freiwilliger__user=request.user)[0]
        
        action = request.POST.get('action')
        if action == 'unpend':
            freiwilliger_aufgaben.pending = False
            freiwilliger_aufgaben.erledigt = False
            freiwilliger_aufgaben.erledigt_am = None
        else:  # action == 'pending'
            freiwilliger_aufgaben.pending = True
            freiwilliger_aufgaben.erledigt = False
            freiwilliger_aufgaben.erledigt_am = datetime.now()

        freiwilliger_aufgaben.save()
        return redirect('aufgaben')

    aufgabe_exists = Aufgabe.objects.filter(id=aufgabe_id).exists()
    if not aufgabe_exists:
        return redirect('aufgaben')

    requested_aufgabe = Aufgabe.objects.get(id=aufgabe_id)

    print(requested_aufgabe)

    freiwilliger_aufgaben_exists = FreiwilligerAufgaben.objects.filter(aufgabe=requested_aufgabe,
                                                                       freiwilliger__user=request.user).exists()

    if not freiwilliger_aufgaben_exists:
        # return redirect('aufgaben')
        pass

    freiwilliger_aufgaben = FreiwilligerAufgaben.objects.filter(aufgabe=requested_aufgabe, freiwilliger__user=request.user)[0]

    context = {
        'aufgabe': requested_aufgabe,
        'freiwilliger_aufgaben': freiwilliger_aufgaben
    }
    return render(request, 'aufgabe.html', context=context)



@login_required
def bilder(request):
    bilder = Bilder.objects.filter(org=request.user.org).order_by('-date_created')

    data = [
        {
            'bilder': bilder_obj,
            'images': BilderGallery.objects.filter(bilder=bilder_obj)
        }
        for bilder_obj in bilder
    ]

    context = {
        'bilder': bilder,
        'bilder_gallery': data
    }
    return render(request, 'bilder.html', context=context)



@login_required
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

            return redirect('fwhome')
        else:
            form_errors = bilder_form.errors

    bilder_form = BilderForm()
    bilder_gallery_form = BilderGalleryForm()
    
    context = {
        'bilder_form': bilder_form,
        'bilder_gallery_form': bilder_gallery_form,
        'form_errors': form_errors
    }

    return render(request, 'bild.html', context=context)


@login_required
def remove_bild(request):
    gallery_image_id = request.GET.get('galleryImageId', None)
    bild_id = request.GET.get('bildId', None)

    if not gallery_image_id and not bild_id:
        messages.error(request, 'Kein Bild gefunden')
        return redirect('profil')

    try:
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
def remove_bild_all(request):
    bild_id = request.GET.get('bild_id', None)
    if not bild_id:
        messages.error(request, 'Kein Bild gefunden')
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
def dokumente(request):
    ordners = Ordner.objects.filter(org=request.user.org).order_by('ordner_name')

    folder_structure = []

    for ordner in ordners:
        folder_structure.append({
            'ordner': ordner,
            'dokumente': Dokument.objects.filter(org=request.user.org, ordner=ordner).order_by('-date_created')
        })

    context = {
        'ordners': ordners,
        'folder_structure': folder_structure
    }

    return render(request, 'dokumente.html', context=context)



@login_required
def add_dokument(request):
    if request.method == 'POST':
        ordner = Ordner.objects.get(id=request.POST.get('ordner'))
        titel = request.POST.get('titel')
        beschreibung = request.POST.get('beschreibung')
        dokument = request.FILES.get('dokument')

        if dokument:
            Dokument.objects.create(
                org=request.user.org,
                ordner=ordner,
                titel=titel,
                beschreibung=beschreibung,
                dokument=dokument,
                date_created=datetime.now()
            )

    return redirect('dokumente')


@login_required
def add_ordner(request):
    if request.method == 'POST':
        ordner_name = request.POST.get('ordner_name')
        Ordner.objects.create(org=request.user.org, ordner_name=ordner_name)
    return redirect('dokumente')


@login_required
def serve_logo(request, image_name):
    # Define the path to the image directory
    image_path = os.path.join(settings.LOGOS_PATH, image_name)

    print('image_path:', image_path)

    # Check if the file exists
    if not os.path.exists(image_path):
        raise Http404("Image does not exist")

    # Open the image file in binary mode
    with open(image_path, 'rb') as img_file:
        # Determine the content type (you might want to use a library to detect this)
        content_type = 'image/jpeg'  # Change this if your images are in different formats
        response = HttpResponse(img_file.read(), content_type=content_type)
        response['Content-Disposition'] = f'inline; filename="{image_name}"'
        return response


def get_bild(image_path, image_name):
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
def serve_bilder(request, image_name):
    # Define the path to the image directory
    image_path = os.path.join(settings.BILDER_PATH, image_name)
    return get_bild(image_path, image_name)


@login_required
def serve_small_bilder(request, image_name):
    # Define the path to the image directory
    image_path = os.path.join(settings.BILDER_PATH, 'small', image_name)
    return get_bild(image_path, image_name)


def get_mimetype(doc_path):
    mime_type, _ = mimetypes.guess_type(doc_path)
    return mime_type


def pdf_to_image(doc_path):
    from pdf2image import convert_from_path
    image = convert_from_path(doc_path, first_page=1, last_page=1)[0]
    img_path = os.path.join('dokument', 'temp.jpg')
    image.save(img_path)
    response = get_bild(img_path, img_path.split('/')[-1])
    os.remove(img_path)
    return response



@login_required
def serve_dokument(request, org_name, ordner_name, dokument_name):
    img = request.GET.get('img', None)
    download = request.GET.get('download', None)
    # Define the path to the image directory
    org = request.user.org
    if not org or org.name != org_name:
        raise Http404("Dokument does not exist")

    doc_path = os.path.join('dokument', org_name, ordner_name, dokument_name)

    if not os.path.exists(doc_path):
        raise Http404("Dokument does not exist")

    mimetype = get_mimetype(doc_path)
    if mimetype and mimetype.startswith('image') and not download:
        return get_bild(doc_path, dokument_name)

    if img and not download:
        if mimetype and mimetype == 'application/pdf':
            return pdf_to_image(doc_path)

        if dokument_name.endswith('.docx') or dokument_name.endswith('.doc'):
            command = ["abiword", "--to=pdf", doc_path]
            try:
                subprocess.run(command)
                if dokument_name.endswith('.docx'):
                    doc_path = doc_path.replace('.docx', '.pdf')
                else:
                    doc_path = doc_path.replace('.doc', '.pdf')
                return pdf_to_image(doc_path)
            except Exception as e:
                print(e)
                return HttpResponse(e)

    with open(doc_path, 'rb') as file:
        response = HttpResponse(file.read(), content_type=mimetype or 'application/octet-stream')
        response['Content-Disposition'] = f'attachment; filename="{doc_path.split("/")[-1]}"'
        return response


@login_required
def remove_dokument(request):
    if request.method == 'POST':
        dokument_id = request.POST.get('dokument_id')
        try:
            dokument = Dokument.objects.get(id=dokument_id, org=request.user.org)
            dokument.delete()
        except Dokument.DoesNotExist:
            pass
    return redirect('dokumente')


@login_required
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
