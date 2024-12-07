import os
from datetime import datetime
import mimetypes
import subprocess

from django.contrib import messages
from django.db.models import Count
from django.shortcuts import render, redirect
from .models import Freiwilliger, Aufgabe, FreiwilligerAufgabenprofil, FreiwilligerAufgaben, Post, Bilder, CustomUser, \
    BilderGallery, Ampel
from ORG.models import Dokument, Ordner
from django.http import HttpResponse, Http404

from .forms import BilderForm, BilderGalleryForm


def getOrg(request):
    if request.user.is_authenticated:
        if CustomUser.objects.filter(user=request.user).exists():
            return CustomUser.objects.get(user=request.user).org
    return None


# Create your views here.
def home(request):
    # freiwilliger_aufgaben = (
    #     FreiwilligerAufgaben.objects
    #     .filter(freiwilliger__user=request.user)
    #     .values('aufgabe__name', 'aufgabe__beschreibung', 'erledigt')
    #     .distinct()
    #     .order_by('aufgabe__name')
    # )

    if not request.user.is_authenticated:
        return redirect('login')

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

    freiwilliger_aufgaben = {
        'erledigt': erledigte_aufgaben,
        'erledigt_prozent': round(len_erledigt / gesamt * 100) if gesamt > 0 else 0,
        'pending': pending_aufgaben,
        'pending_prozent': round(len_pending / gesamt * 100) if gesamt > 0 else 0,
        'offen': offene_aufgaben,
        'offen_prozent': round(len_offen / gesamt * 100) if gesamt > 0 else 0,
    }

    bilder = Bilder.objects.filter(org=getOrg(request)).order_by('-date_created')
    bilder_data = [
        {
            'bilder': bilder_obj,
            'images': BilderGallery.objects.filter(bilder=bilder_obj)
        }
        for bilder_obj in bilder[:2]
    ]

    last_three_posts = Post.objects.all().order_by('date')[:3]

    context = {
        'aufgaben': freiwilliger_aufgaben,
        'bilder': bilder_data,
        'posts': last_three_posts,
    }

    return render(request, 'home.html', context=context)


def profil(request):
    return render(request, 'profil.html')


def ampel(request):
    ampel = request.GET.get('ampel', None)
    if ampel and ampel.upper() in ['R', 'G', 'Y']:
        ampel = ampel.upper()
        comment = request.GET.get('comment', None)
        freiwilliger = Freiwilliger.objects.get(user=request.user)
        ampel_object = Ampel.objects.create(freiwilliger=freiwilliger, status=ampel, org=getOrg(request), comment=comment)
        ampel_object.save()


        msg_text = 'Ampel erfolgreich auf ' + ('Grün' if ampel == 'G' else 'Rot' if ampel == 'R' else 'Gelb' if ampel == 'Y' else 'error') + ' gesetzt'

        messages.success(request, msg_text)
        return redirect('fwhome')

    last_ampel = Ampel.objects.filter(freiwilliger__user=request.user).order_by('-date').first()

    return render(request, 'ampel.html', context={'last_ampel': last_ampel})


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


def aufgabe(request, aufgabe_id):
    if request.method == 'POST':
        requested_aufgabe = Aufgabe.objects.get(id=aufgabe_id)
        freiwilliger_aufgaben = \
            FreiwilligerAufgaben.objects.filter(aufgabe=requested_aufgabe, freiwilliger__user=request.user)[0]
        freiwilliger_aufgaben.pending = True
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

    freiwilliger_aufgaben = \
        FreiwilligerAufgaben.objects.filter(aufgabe=requested_aufgabe, freiwilliger__user=request.user)[0]

    context = {
        'aufgabe': requested_aufgabe,
        'freiwilliger_aufgaben': freiwilliger_aufgaben
    }
    return render(request, 'aufgabe.html', context=context)


def bilder(request):
    bilder = Bilder.objects.filter(org=getOrg(request)).order_by('-date_created')

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


def bild(request):
    form_errors = None

    if request.POST:
        org = getOrg(request)
        bilder_form = BilderForm(request.POST)
        images = request.FILES.getlist('image')

        if bilder_form.is_valid() and len(images) > 0:

            bilder_form_data = bilder_form.cleaned_data

            bilder, created = Bilder.objects.get_or_create(
                org=org,
                user=request.user,
                titel=bilder_form_data['titel'],
                beschreibung=bilder_form_data['beschreibung'],
                defaults={'date_created': datetime.now(), 'date_updated': datetime.now()}
            )

            if not created:
                bilder.date_updated = datetime.now()
                bilder.save()

            def get_smaller_image(image):
                from PIL import Image
                import io
                from django.core.files.base import ContentFile

                img = Image.open(image)
                img.thumbnail((1000, 1000))

                img_io = io.BytesIO()
                format = img.format if img.format in ["JPEG", "PNG"] else "JPEG"
                img.save(img_io, format=format)
                extension = format.lower()
                filename = f"{image.name.rsplit('.', 1)[0]}.{extension}"
                return ContentFile(img_io.getvalue(), name=filename)

            # Save each image with a reference to the product
            for image in images:
                BilderGallery.objects.create(
                    org=org,
                    bilder=bilder,
                    small_image=get_smaller_image(image),
                    image=image
                )

            return redirect('fwhome')
        else:
            form_errors = bilder_form.errors

    bilder_form = BilderForm()
    bilder_gallery_form = BilderGalleryForm()

    context = {
        'form_errors': form_errors,
        'bilder_form': bilder_form,
        'bilder_gallery_form': bilder_gallery_form
    }

    return render(request, 'bild.html', context=context)


def dokumente(request):
    ordners = Ordner.objects.filter(org=getOrg(request)).order_by('ordner_name')

    folder_structure = []

    for ordner in ordners:
        folder_structure.append({
            'ordner': ordner,
            'dokumente': Dokument.objects.filter(org=getOrg(request), ordner=ordner).order_by('-date_created')
        })

    context = {
        'ordners': ordners,
        'folder_structure': folder_structure
    }

    return render(request, 'dokumente.html', context=context)


def add_dokument(request):
    if request.method == 'POST':
        org = getOrg(request)
        ordner = Ordner.objects.get(id=request.POST.get('ordner'))
        beschreibung = request.POST.get('beschreibung')
        dokument = request.FILES.get('dokument')

        if dokument:
            Dokument.objects.create(
                org=org,
                ordner=ordner,
                beschreibung=beschreibung,
                dokument=dokument,
                date_created=datetime.now()
            )

    return redirect('dokumente')


def serve_logo(request, image_name):
    # Define the path to the image directory
    image_path = os.path.join('logos', image_name)

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


def serve_bilder(request, image_name):
    # Define the path to the image directory
    image_path = os.path.join('bilder', image_name)
    return get_bild(image_path, image_name)


def serve_small_bilder(request, image_name):
    # Define the path to the image directory
    image_path = os.path.join('bilder/small', image_name)
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


def serve_dokument(request, org_name, ordner_name, dokument_name):
    img = request.GET.get('img', None)
    # Define the path to the image directory
    org = getOrg(request)
    if not org or org.name != org_name:
        raise Http404("Dokument does not exist")

    doc_path = os.path.join('dokument', org_name, ordner_name, dokument_name)

    if not os.path.exists(doc_path):
        raise Http404("Dokument does not exist")

    mimetype = get_mimetype(doc_path)
    if mimetype and mimetype.startswith('image'):
        return get_bild(doc_path, dokument_name)

    if img:
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
            # return HttpResponse('Not supported yet')

    with open(doc_path, 'rb') as file:
        if mimetype:
            response = HttpResponse(file.read(), content_type=mimetype)
        else:
            response = HttpResponse(file.read())
            response['Content-Disposition'] = f'attachment; filename="{doc_path.split("/")[-1]}"'
        return response
