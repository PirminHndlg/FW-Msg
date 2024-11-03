import os
from datetime import datetime

from django.db.models import Count
from django.shortcuts import render, redirect
from .models import Freiwilliger, Aufgabe, FreiwilligerAufgabenprofil, FreiwilligerAufgaben, Post, Bilder, CustomUser, \
    BilderGallery
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
        'erledigt_prozent': round(len_erledigt / gesamt * 100),
        'pending': pending_aufgaben,
        'pending_prozent': round(len_pending / gesamt * 100),
        'offen': offene_aufgaben,
        'offen_prozent': round(len_offen / gesamt * 100),
    }

    bilder = Bilder.objects.filter(org=getOrg(request)).order_by('date_created')
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
    return render(request, 'ampel.html')


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
        'erledigt_prozent': round(len_erledigt / gesamt * 100),
        'len_pending': len_pending,
        'pending_prozent': round(len_pending / gesamt * 100),
        'len_offen': len_offen,
        'offen_prozent': round(len_offen / gesamt * 100),
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
    bilder = Bilder.objects.filter(org=getOrg(request)).order_by('date_created')

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
        bilder_gallery_form = BilderGalleryForm(request.POST)
        images = request.FILES.getlist('image')
        print(len(images))
        print(bilder_form.is_valid())
        print(bilder_form.cleaned_data)
        print(org)

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

            # Save each image with a reference to the product
            for image in images:
                BilderGallery.objects.create(
                    org=org,
                    bilder=bilder,
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


def serve_bilder(request, image_name):
    # Define the path to the image directory
    image_path = os.path.join('bilder', image_name)

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
