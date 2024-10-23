from django.shortcuts import render
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

    aufgaben_erledigt = FreiwilligerAufgaben.objects.filter(freiwilliger__user=request.user, erledigt=True).count()
    aufgaben_offen = FreiwilligerAufgaben.objects.filter(freiwilliger__user=request.user, erledigt=False,
                                                         pending=False).count()
    aufgaben_pending = FreiwilligerAufgaben.objects.filter(freiwilliger__user=request.user, erledigt=False,
                                                           pending=True).count()
    gesamt = aufgaben_erledigt + aufgaben_offen

    freiwilliger_aufgaben = {
        'erledigt': aufgaben_erledigt,
        'erledigt_prozent': round(aufgaben_erledigt / gesamt * 100),
        'pending': aufgaben_pending,
        'pending_prozent': round(aufgaben_pending / gesamt * 100),
        'offen': aufgaben_offen,
        'offen_prozent': round(aufgaben_offen / gesamt * 100),
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
    return render(request, 'aufgaben.html')
