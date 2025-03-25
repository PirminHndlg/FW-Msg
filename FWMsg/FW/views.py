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
from django.utils.translation import gettext as _
from .forms import BilderForm, BilderGalleryForm#, ProfilUserForm
from Global.models import (
    Freiwilliger, Aufgabe, 
    UserAufgaben, Post, Bilder, CustomUser,
    BilderGallery, Ampel, ProfilUser, Notfallkontakt, Referenten
)
#from ORG.forms import AddNotfallkontaktForm

from FWMsg.decorators import required_role
from .templatetags.base_fw_filter import get_auswaeriges_amt_link, format_text_with_link

from Global.views import get_bilder

@login_required
@required_role('F')
def home(request):
    """Dashboard view showing tasks, images and posts."""
    # Get task statistics
    task_queryset = UserAufgaben.objects.filter(user=request.user)
    
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

    user_aufgaben = {
        'erledigt': erledigte_aufgaben,
        'erledigt_prozent': safe_percentage(len_erledigt, gesamt),
        'pending': pending_aufgaben,
        'pending_prozent': safe_percentage(len_pending, gesamt),
        'offen': offene_aufgaben[:3],
        'offen_prozent': safe_percentage(len_offen, gesamt),
    }

    # Get recent images
    gallery_images = get_bilder(request.user.org)

    freiwilliger = Freiwilliger.objects.get(user=request.user) if Freiwilliger.objects.filter(user=request.user).exists() else None

    if freiwilliger and (freiwilliger.start_real or freiwilliger.start_geplant):
        days_until_start = ((freiwilliger.start_real or freiwilliger.start_geplant) - datetime.now().date()).days
    else:
        days_until_start = None

    context = {
        'aufgaben': user_aufgaben,
        'gallery_images': gallery_images,
        'posts': Post.objects.all().order_by('date')[:3],
        'freiwilliger': freiwilliger,
        'days_until_start': days_until_start,
    }

    return render(request, 'home.html', context=context)


@login_required
@required_role('F')
def ampel(request):
    ampel = request.POST.get('ampel', None)
    if ampel and ampel.upper() in ['R', 'G', 'Y']:
        ampel = ampel.upper()
        comment = request.POST.get('ampel_comment', None)
        ampel_object = Ampel.objects.create(
            user=request.user, 
            status=ampel, 
            org=request.user.org,
            comment=comment
        )
        ampel_object.save()

        msg_text = 'Ampel erfolgreich auf ' + (
            'Grün' if ampel == 'G' else 'Rot' if ampel == 'R' else 'Gelb' if ampel == 'Y' else 'error') + ' gesetzt'

        messages.success(request, msg_text)
        return redirect('fw_home')

    last_ampel = Ampel.objects.filter(user=request.user).order_by('-date').first()

    return render(request, 'ampel.html', context={'last_ampel': last_ampel})



@login_required
@required_role('F')
def aufgaben(request):
    erledigte_aufgaben = UserAufgaben.objects.filter(user=request.user, erledigt=True).order_by(
        'faellig')
    offene_aufgaben = UserAufgaben.objects.filter(user=request.user, erledigt=False,
                                                          pending=False).order_by('faellig')
    pending_aufgaben = UserAufgaben.objects.filter(user=request.user, erledigt=False,
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

    user_aufgabe_exists = UserAufgaben.objects.filter(id=aufgabe_id).exists()
    if not user_aufgabe_exists:
        return redirect('aufgaben')
    user_aufgabe = UserAufgaben.objects.get(id=aufgabe_id)
    
    if request.method == 'POST':
        file = request.FILES.get('file')
        
        if file and user_aufgabe.aufgabe.mitupload:
            user_aufgabe.file = file
        
        action = request.POST.get('action')
        if action == 'unpend':
            user_aufgabe.pending = False
            user_aufgabe.erledigt = False
            user_aufgabe.erledigt_am = None
        else:  # action == 'pending'
            if user_aufgabe.aufgabe.requires_submission:
                user_aufgabe.pending = True
                user_aufgabe.erledigt = False
            else:
                user_aufgabe.pending = False
                user_aufgabe.erledigt = True

            from ORG.tasks import send_aufgabe_erledigt_email_task
            send_aufgabe_erledigt_email_task.delay(user_aufgabe.id)

            user_aufgabe.erledigt_am = datetime.now()


        user_aufgabe.save()
        base_url = reverse('aufgaben')
        if action == 'pending':
            return redirect(f'{base_url}?show_confetti=true')
        return redirect(base_url)


    context = {
        'freiwilliger_aufgabe': user_aufgabe
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
                'title': _('Reisehinweise'),
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
                'title': _('Notfallnummern'),
                'items': [
                    {'icon': 'telephone-fill', 'value': format_text_with_link(land.notfallnummern)}
                ]
            })

    # Add embassy and consulate cards if einsatzstelle exists and has the data
    if freiwilliger.einsatzstelle:
        if freiwilliger.einsatzstelle.botschaft:
            country_cards.append({
                'title': _('Botschaft'),
                'items': [
                    {'icon': 'building', 'value': format_text_with_link(freiwilliger.einsatzstelle.botschaft)}
                ]
            })
        
        if freiwilliger.einsatzstelle.konsulat:
            country_cards.append({
                'title': _('Konsulat'),
                'items': [
                    {'icon': 'building', 'value': format_text_with_link(freiwilliger.einsatzstelle.konsulat)}
                ]
            })

    # Prepare location cards
    location_cards = []
    if freiwilliger.einsatzstelle:
        if freiwilliger.einsatzstelle.arbeitsvorgesetzter:
            location_cards.append({
                'title': _('Arbeitsvorgesetzte:r'),
                'items': [
                    {'icon': 'person', 'value': format_text_with_link(freiwilliger.einsatzstelle.arbeitsvorgesetzter)}
                ]
            })
        
        if freiwilliger.einsatzstelle.partnerorganisation:
            location_cards.append({
                'title': _('Partnerorganisation'),
                'items': [
                    {'icon': 'building', 'value': format_text_with_link(freiwilliger.einsatzstelle.partnerorganisation)}
                ]
            })
        
        if freiwilliger.einsatzstelle.mentor:
            location_cards.append({
                'title': _('Mentor:in'),
                'items': [
                    {'icon': 'person', 'value': format_text_with_link(freiwilliger.einsatzstelle.mentor)}
                ]
            })

    # Prepare general cards
    general_cards = []
    if land:
        if land.arztpraxen:
            general_cards.append({
                'title': _('Arztpraxen'),
                'items': [
                    {'icon': 'hospital', 'value': format_text_with_link(land.arztpraxen)}
                ]
            })
        
        if land.apotheken:
            general_cards.append({
                'title': _('Apotheken'),
                'items': [
                    {'icon': 'capsule', 'value': format_text_with_link(land.apotheken)}
                ]
            })
        
        if land.informationen:
            general_cards.append({
                'title': _('Weitere Informationen'),
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
