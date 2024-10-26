import os

from django.shortcuts import render, redirect
from .models import Aufgabe, FreiwilligerAufgabenprofil, FreiwilligerAufgaben, Post
from django.http import HttpResponse, Http404


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

    last_three_posts = Post.objects.all().order_by('date')[:3]

    context = {
        'aufgaben': freiwilliger_aufgaben,
        'posts': last_three_posts
    }

    return render(request, 'home.html', context=context)


def profil(request):
    return render(request, 'profil.html')


def ampel(request):
    return render(request, 'ampel.html')


def aufgaben(request):
    erledigte_aufgaben = FreiwilligerAufgaben.objects.filter(freiwilliger__user=request.user, erledigt=True).order_by('faellig')
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


def serve_image(request, image_name):
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