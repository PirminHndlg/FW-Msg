from django.shortcuts import render, redirect
from .models import Aufgabe, FreiwilligerAufgabenprofil, FreiwilligerAufgaben, Post
from django.http import HttpResponse


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
