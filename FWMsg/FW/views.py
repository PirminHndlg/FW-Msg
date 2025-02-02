from datetime import datetime
import mimetypes
import os
import subprocess
import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import HttpResponse, Http404
from django.shortcuts import render, redirect
from django.conf import settings
from functools import wraps
from django.urls import reverse

from .forms import BilderForm, BilderGalleryForm, ProfilUserForm
from .models import (
    Freiwilliger, Aufgabe, FreiwilligerAufgabenprofil, 
    FreiwilligerAufgaben, Post, Bilder, CustomUser,
    BilderGallery, Ampel, ProfilUser, Notfallkontakt
)
from ORG.models import Dokument, Ordner, Referenten
from ORG.forms import AddNotfallkontaktForm

from FWMsg.decorators import required_role

from Global.views import get_bilder

@login_required
@required_role('F')
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
    gallery_images = get_bilder(request)

    context = {
        'aufgaben': freiwilliger_aufgaben,
        'gallery_images': gallery_images,
        'posts': Post.objects.all().order_by('date')[:3],
    }

    return render(request, 'home.html', context=context)


@login_required
@required_role('F')
def ampel(request):
    ampel = request.POST.get('ampel', None)
    if ampel and ampel.upper() in ['R', 'G', 'Y']:
        ampel = ampel.upper()
        comment = request.POST.get('ampel_comment', None)
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
        return redirect('fw_home')

    last_ampel = Ampel.objects.filter(freiwilliger__user=request.user).order_by('-date').first()

    return render(request, 'ampel.html', context={'last_ampel': last_ampel})



@login_required
@required_role('F')
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

    # Create calendar events
    calendar_events = []
    
    # Add open tasks (blue)
    for aufgabe in offene_aufgaben:
        calendar_events.append({
            'title': aufgabe.aufgabe.name,
            'start': aufgabe.faellig.strftime('%Y-%m-%d') if aufgabe.faellig else '',
            'url': reverse('aufgaben_detail', args=[aufgabe.aufgabe.id]),
            'backgroundColor': '#0d6efd',
            'borderColor': '#0d6efd'
        })
    
    # Add pending tasks (yellow)
    for aufgabe in pending_aufgaben:
        calendar_events.append({
            'title': aufgabe.aufgabe.name,
            'start': aufgabe.faellig.strftime('%Y-%m-%d') if aufgabe.faellig else '',
            'url': reverse('aufgaben_detail', args=[aufgabe.aufgabe.id]),
            'backgroundColor': '#ffc107',
            'borderColor': '#ffc107',
            'textColor': '#000'
        })
    
    # Add completed tasks (green)
    for aufgabe in erledigte_aufgaben:
        calendar_events.append({
            'title': aufgabe.aufgabe.name,
            'start': aufgabe.faellig.strftime('%Y-%m-%d') if aufgabe.faellig else '',
            'url': reverse('aufgaben_detail', args=[aufgabe.aufgabe.id]),
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
    return render(request, 'aufgaben.html', context=context)


@login_required
@required_role('F')
def aufgabe(request, aufgabe_id):
    if request.method == 'POST':
        requested_aufgabe = Aufgabe.objects.get(id=aufgabe_id)
        file = request.FILES.get('file')
        freiwilliger_aufgaben = \
            FreiwilligerAufgaben.objects.filter(aufgabe=requested_aufgabe, freiwilliger__user=request.user)[0]
        
        if file and freiwilliger_aufgaben.aufgabe.mitupload:
            freiwilliger_aufgaben.file = file
        
        action = request.POST.get('action')
        if action == 'unpend':
            freiwilliger_aufgaben.pending = False
            freiwilliger_aufgaben.erledigt = False
            freiwilliger_aufgaben.erledigt_am = None
        else:  # action == 'pending'
            if requested_aufgabe.requires_submission:
                freiwilliger_aufgaben.pending = True
                freiwilliger_aufgaben.erledigt = False
            else:
                freiwilliger_aufgaben.pending = False
                freiwilliger_aufgaben.erledigt = True

            freiwilliger_aufgaben.erledigt_am = datetime.now()


        freiwilliger_aufgaben.save()
        base_url = reverse('aufgaben')
        if action == 'pending':
            return redirect(f'{base_url}?show_confetti=true')
        return redirect(base_url)

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
@required_role('F')
def laenderinfo(request):
    user = request.user
    org = user.org
    freiwilliger = Freiwilliger.objects.get(user=user)
    land = freiwilliger.einsatzland
    referenten = Referenten.objects.filter(org=org, land=land)
    return render(request, 'laenderinfo.html', context={'referenten': referenten, 'freiwilliger': freiwilliger})

@login_required
@required_role('F')
def notfallkontakte(request):
    if request.method == 'POST':
        form = AddNotfallkontaktForm(request.POST)
        if form.is_valid():
            form.instance.org = request.user.org
            form.instance.freiwilliger = Freiwilliger.objects.get(user=request.user)
            form.save()
            return redirect('notfallkontakte')
        else:
            messages.error(request, 'Fehler beim Hinzufügen des Notfallkontakts')
    form = AddNotfallkontaktForm()
    form.fields['freiwilliger'].widget = form.fields['freiwilliger'].hidden_widget()
    notfallkontakte = Notfallkontakt.objects.filter(freiwilliger__user=request.user)
    return render(request, 'notfallkontakte.html', context={'form': form, 'notfallkontakte': notfallkontakte})
