from datetime import datetime
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.utils.translation import gettext as _
from Global.models import (
    UserAufgaben, Post2,
)
from FW.models import Freiwilliger
from TEAM.models import Team

from FWMsg.decorators import required_role
from .templatetags.base_fw_filter import get_auswaeriges_amt_link, format_text_with_link


base_template = 'baseFw.html'

@login_required
@required_role('F')
def home(request):
    """Dashboard view showing tasks, images and posts."""
    from Global.views import get_bilder
    
    # Get task statistics
    user_aufgaben = None
    if request.user.customuser.person_cluster and request.user.customuser.person_cluster.aufgaben:
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
    if request.user.customuser.person_cluster and request.user.customuser.person_cluster.bilder:
        gallery_images = get_bilder(request.user.org)
    else:
        gallery_images = []

    freiwilliger = Freiwilliger.objects.get(user=request.user) if Freiwilliger.objects.filter(user=request.user).exists() else None

    if freiwilliger and (freiwilliger.start_real or freiwilliger.start_geplant):
        days_until_start = ((freiwilliger.start_real or freiwilliger.start_geplant) - datetime.now().date()).days
    else:
        days_until_start = None

    context = {
        'aufgaben': user_aufgaben,
        'gallery_images': gallery_images,
        'posts': Post2.objects.all().order_by('date')[:3],
        'freiwilliger': freiwilliger,
        'days_until_start': days_until_start,
    }

    return render(request, 'home.html', context=context)

@login_required
@required_role('F')
def laenderinfo(request):
    user = request.user
    freiwilliger = Freiwilliger.objects.get(user=user)
    land = freiwilliger.einsatzland2
    referenten = Team.objects.filter(org=user.org, land=land) if land else []

    # Prepare organization cards
    org_cards = []
    if freiwilliger.org:
        org_cards.append({
            'title': freiwilliger.org.name,
            'items': [
                {'icon': 'telephone-fill', 'value': freiwilliger.org.telefon},
                {'icon': 'globe', 'type': 'link', 'value': freiwilliger.org.website, 'url': freiwilliger.org.website, 'external': True} if freiwilliger.org.website else None,
                {'icon': 'envelope-fill', 'type': 'email', 'value': freiwilliger.org.email},
                # {'icon': 'file-earmark-text-fill', 'value': freiwilliger.entsendeform.name if hasattr(freiwilliger, 'entsendeform') and freiwilliger.entsendeform else None, 'label': 'Entsendeform'}
            ]
        })

    # Add referent cards
    for referent in referenten:
        org_cards.append({
            'title': f"Ansprechpartner:in {referent.user.first_name} {referent.user.last_name}",
            'items': [
                # {'icon': 'telephone-fill', 'value': f"{referent.user.phone_work} (Arbeit)" if referent.user.phone_work else None},
                # {'icon': 'telephone-fill', 'value': f"{referent.user.phone_mobil} (Mobil)" if referent.user.phone_mobil else None},
                {'icon': 'envelope-fill', 'type': 'email', 'value': referent.user.email},
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
                        'icon': 'link',
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
    if freiwilliger.einsatzstelle2:
        if freiwilliger.einsatzstelle2.botschaft:
            country_cards.append({
                'title': _('Botschaft'),
                'items': [
                    {'icon': 'building', 'value': format_text_with_link(freiwilliger.einsatzstelle2.botschaft)}
                ]
            })
        
        if freiwilliger.einsatzstelle2.konsulat:
            country_cards.append({
                'title': _('Konsulat'),
                'items': [
                    {'icon': 'building', 'value': format_text_with_link(freiwilliger.einsatzstelle2.konsulat)}
                ]
            })

    # Prepare location cards
    location_cards = []
    if freiwilliger.einsatzstelle2:
        if freiwilliger.einsatzstelle2.arbeitsvorgesetzter:
            location_cards.append({
                'title': _('Arbeitsvorgesetzte:r'),
                'items': [
                    {'icon': 'person', 'value': format_text_with_link(freiwilliger.einsatzstelle2.arbeitsvorgesetzter)}
                ]
            })
        
        if freiwilliger.einsatzstelle2.partnerorganisation:
            location_cards.append({
                'title': _('Partnerorganisation'),
                'items': [
                    {'icon': 'building', 'value': format_text_with_link(freiwilliger.einsatzstelle2.partnerorganisation)}
                ]
            })
        
        if freiwilliger.einsatzstelle2.mentor:
            location_cards.append({
                'title': _('Mentor:in'),
                'items': [
                    {'icon': 'person', 'value': format_text_with_link(freiwilliger.einsatzstelle2.mentor)}
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
