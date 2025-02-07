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
from .templatetags.base_filter import get_auswaeriges_amt_link, format_text_with_link

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
    gallery_images = get_bilder(request.user.org)

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
    return render(request, 'aufgaben.html', context=context)


@login_required
@required_role('F')
def aufgabe(request, aufgabe_id):

    freiwilliger_aufgabe_exists = FreiwilligerAufgaben.objects.filter(id=aufgabe_id).exists()
    if not freiwilliger_aufgabe_exists:
        return redirect('aufgaben')
    freiwilliger_aufgabe = FreiwilligerAufgaben.objects.get(id=aufgabe_id)
    
    if request.method == 'POST':
        file = request.FILES.get('file')
        
        if file and freiwilliger_aufgabe.aufgabe.mitupload:
            freiwilliger_aufgabe.file = file
        
        action = request.POST.get('action')
        if action == 'unpend':
            freiwilliger_aufgabe.pending = False
            freiwilliger_aufgabe.erledigt = False
            freiwilliger_aufgabe.erledigt_am = None
        else:  # action == 'pending'
            if freiwilliger_aufgabe.aufgabe.requires_submission:
                freiwilliger_aufgabe.pending = True
                freiwilliger_aufgabe.erledigt = False
            else:
                freiwilliger_aufgabe.pending = False
                freiwilliger_aufgabe.erledigt = True

            freiwilliger_aufgabe.erledigt_am = datetime.now()


        freiwilliger_aufgabe.save()
        base_url = reverse('aufgaben')
        if action == 'pending':
            return redirect(f'{base_url}?show_confetti=true')
        return redirect(base_url)


    context = {
        'freiwilliger_aufgabe': freiwilliger_aufgabe
    }
    return render(request, 'aufgabe.html', context=context)


@login_required
@required_role('F')
def laenderinfo(request):
    user = request.user
    freiwilliger = Freiwilliger.objects.get(user=user)
    land = freiwilliger.einsatzland
    referenten = Referenten.objects.filter(org=user.org, land=land) if land else []

    # Prepare organization cards
    org_cards = []
    if freiwilliger.org:
        org_cards.append({
            'title': freiwilliger.org.name,
            'items': [
                {'icon': 'telephone-fill', 'value': freiwilliger.org.telefon},
                {'icon': 'globe', 'type': 'link', 'value': freiwilliger.org.website, 'url': freiwilliger.org.website, 'external': True} if freiwilliger.org.website else None,
                {'icon': 'envelope-fill', 'type': 'email', 'value': freiwilliger.org.email},
                {'icon': 'file-earmark-text-fill', 'value': freiwilliger.entsendeform.name if hasattr(freiwilliger, 'entsendeform') and freiwilliger.entsendeform else None, 'label': 'Entsendeform'}
            ]
        })

    # Add referent cards
    for referent in referenten:
        org_cards.append({
            'title': f"Referent:in {referent.first_name} {referent.last_name}",
            'items': [
                {'icon': 'telephone-fill', 'value': f"{referent.phone_work} (Arbeit)" if referent.phone_work else None},
                {'icon': 'telephone-fill', 'value': f"{referent.phone_mobil} (Mobil)" if referent.phone_mobil else None},
                {'icon': 'envelope-fill', 'type': 'email', 'value': referent.email},
                {'icon': 'globe', 'value': ', '.join(land.name for land in referent.land.all()) if referent.land.exists() else None}
            ]
        })

    # Prepare country cards
    country_cards = []
    if land:
        country_cards = [
            {
                'title': 'Reisehinweise',
                'items': [
                    {
                        'icon': 'box-arrow-up-right',
                        'type': 'link',
                        'value': 'Auswärtiges Amt',
                        'url': get_auswaeriges_amt_link(land.name),
                        'external': True
                    }
                ]
            }
        ]
        
        if land.notfallnummern:
            country_cards.append({
                'title': 'Notfallnummern',
                'items': [
                    {'icon': 'telephone-fill', 'value': format_text_with_link(land.notfallnummern)}
                ]
            })

    # Add embassy and consulate cards if einsatzstelle exists and has the data
    if freiwilliger.einsatzstelle:
        if freiwilliger.einsatzstelle.botschaft:
            country_cards.append({
                'title': 'Botschaft',
                'items': [
                    {'icon': 'building', 'value': format_text_with_link(freiwilliger.einsatzstelle.botschaft)}
                ]
            })
        
        if freiwilliger.einsatzstelle.konsulat:
            country_cards.append({
                'title': 'Konsulat',
                'items': [
                    {'icon': 'building', 'value': format_text_with_link(freiwilliger.einsatzstelle.konsulat)}
                ]
            })

    # Prepare location cards
    location_cards = []
    if freiwilliger.einsatzstelle:
        if freiwilliger.einsatzstelle.arbeitsvorgesetzter:
            location_cards.append({
                'title': 'Arbeitsvorgesetzte:r',
                'items': [
                    {'icon': 'person', 'value': format_text_with_link(freiwilliger.einsatzstelle.arbeitsvorgesetzter)}
                ]
            })
        
        if freiwilliger.einsatzstelle.partnerorganisation:
            location_cards.append({
                'title': 'Partnerorganisation',
                'items': [
                    {'icon': 'building', 'value': format_text_with_link(freiwilliger.einsatzstelle.partnerorganisation)}
                ]
            })
        
        if freiwilliger.einsatzstelle.mentor:
            location_cards.append({
                'title': 'Mentor:in',
                'items': [
                    {'icon': 'person', 'value': format_text_with_link(freiwilliger.einsatzstelle.mentor)}
                ]
            })

    # Prepare general cards
    general_cards = []
    if land:
        if land.arztpraxen:
            general_cards.append({
                'title': 'Arztpraxen',
                'items': [
                    {'icon': 'hospital', 'value': format_text_with_link(land.arztpraxen)}
                ]
            })
        
        if land.apotheken:
            general_cards.append({
                'title': 'Apotheken',
                'items': [
                    {'icon': 'capsule', 'value': format_text_with_link(land.apotheken)}
                ]
            })
        
        if land.informationen:
            general_cards.append({
                'title': 'Weitere Informationen',
                'width': '8',
                'items': [
                    {'icon': 'info-circle', 'value': format_text_with_link(land.informationen)}
                ]
            })

    context = {
        'referenten': referenten,
        'freiwilliger': freiwilliger,
        'org_cards': org_cards,
        'country_cards': country_cards,
        'location_cards': location_cards,
        'general_cards': general_cards
    }
    return render(request, 'laenderinfo.html', context=context)

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
