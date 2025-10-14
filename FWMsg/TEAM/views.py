from datetime import timedelta
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Count
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone

from FW.models import Freiwilliger
from FWMsg.decorators import required_role
from Global.models import (
    Ampel2, Bilder2, Einsatzland2, Einsatzstelle2, 
    Post2, UserAufgaben, UserAttribute
)
from ORG.views import filter_person_cluster
from TEAM.models import Team

# Base template for team views
base_template = 'baseTeam.html'

# Create your views here.
@login_required
@required_role('T')
def home(request):
    """Team dashboard home view with comprehensive data for team members."""
    team_member = _get_team_member(request)
    
    # Initialize default values
    assigned_countries = []
    freiwillige_count = 0
    einsatzstellen_count = 0
    country_stats = []
    recent_ampel_entries = []
    gallery_images = []
    posts = []
    
    if team_member:
        assigned_countries = team_member.land.all()
        
        if assigned_countries.exists():
            # Get volunteers for assigned countries
            freiwillige = _get_Freiwillige(request)
            freiwillige_count = freiwillige.count()
            freiwillige_users = [fw.user for fw in freiwillige]
            
            # Count placement locations
            einsatzstellen_count = Einsatzstelle2.objects.filter(
                org=team_member.org,
                land__in=assigned_countries
            ).count()
            
            # Get recent ampel entries (last 7 days)
            recent_ampel_entries = Ampel2.objects.filter(
                org=team_member.org,
                user__in=freiwillige_users,
                date__gte=timezone.now() - timedelta(days=7)
            ).select_related('user').order_by('-date')[:10]
            
            # Get recent images from volunteers
            recent_bilder = Bilder2.objects.filter(
                org=team_member.org
            ).select_related('user').order_by('-date_created')[:4]
            
            # Group images by gallery
            for bild in recent_bilder:
                bilder_gallery = bild.bildergallery2_set.all()
                if bilder_gallery.exists():
                    gallery_images.append({
                        bild: list(bilder_gallery)
                    })
            
            # Get recent posts from volunteers
            posts = Post2.objects.filter(
                org=team_member.org,
                person_cluster=team_member.user.person_cluster
            ).select_related('user').order_by('-date')[:3]
            
            # Generate country statistics
            for country in assigned_countries:
                country_freiwillige = Freiwilliger.objects.filter(einsatzland2=country)
                country_einsatzstellen = Einsatzstelle2.objects.filter(land=country)
                
                country_stats.append({
                    'country': country,
                    'freiwillige_count': country_freiwillige.count(),
                    'einsatzstellen_count': country_einsatzstellen.count(),
                })
    
    # Get team member's personal tasks
    my_open_tasks = UserAufgaben.objects.none()
    if team_member:
        my_open_tasks = UserAufgaben.objects.filter(
            org=team_member.org,
            user=request.user,
            erledigt=False,
            pending=False,
        ).select_related('aufgabe').order_by('faellig')
    
    context = {
        'team_member': team_member,
        'assigned_countries': assigned_countries,
        'country_stats': country_stats,
        'freiwillige_count': freiwillige_count,
        'einsatzstellen_count': einsatzstellen_count,
        'recent_ampel_entries': recent_ampel_entries,
        'gallery_images': gallery_images,
        'posts': posts,
        'my_open_tasks': my_open_tasks,
        'today': timezone.now().date(),
    }
    
    return render(request, 'teamHome.html', context)

def _get_team_member(request):
    """Helper function to get the team member record for the current user."""
    return Team.objects.filter(user=request.user).first()

def _get_Freiwillige(request):
    """Get all volunteers that are assigned to countries this team member manages."""
    team_member = _get_team_member(request)
    if team_member:
        countries = team_member.land.all()
        return Freiwilliger.objects.filter(einsatzland2__in=countries)
    return Freiwilliger.objects.none()

@filter_person_cluster
@login_required
@required_role('T')
def contacts(request):
    # Get freiwillige with prefetched user data to reduce queries
    freiwillige_queryset = _get_Freiwillige(request)
    if freiwillige_queryset:
        freiwillige = freiwillige_queryset.select_related('user')
    else:
        freiwillige = Freiwilliger.objects.none()
    
    # Collect all user IDs for efficient attribute queries
    user_ids = [fw.user_id for fw in freiwillige]
    
    # Get all relevant attributes in a single query
    all_attributes = UserAttribute.objects.filter(
        user_id__in=user_ids, 
        attribute__type__in=['P', 'E']
    ).select_related('attribute')
    
    # Group attributes by user for easy access
    user_attributes = {}
    for attr in all_attributes:
        if attr.user_id not in user_attributes:
            user_attributes[attr.user_id] = {'phone': [], 'email': []}
        
        if attr.attribute.type == 'P':
            user_attributes[attr.user_id]['phone'].append(attr.value)
        elif attr.attribute.type == 'E':
            user_attributes[attr.user_id]['email'].append(attr.value)
    
    # Build contact cards
    fw_cards = []
    for fw in freiwillige:
        # Start with basic user info
        full_name = f"{fw.user.first_name} {fw.user.last_name}"
        
        # Initialize with primary email
        items = [{'icon': 'envelope', 'value': fw.user.email, 'type': 'email'}]
        
        # Add additional contact information if available
        if fw.user_id in user_attributes:
            attrs = user_attributes[fw.user_id]
            
            # Add phone numbers
            for phone in attrs['phone']:
                items.append({'icon': 'phone', 'value': phone, 'type': 'phone'})
                
            # Add additional emails
            for email in attrs['email']:
                items.append({'icon': 'envelope', 'value': email, 'type': 'email'})
        
        fw_cards.append({
            'title': full_name,
            'items': items,
            'freiwilliger': fw  # Include the original object for additional data in template
        })
    
    return render(request, 'teamContacts.html', {
        'freiwillige': freiwillige, 
        'fw_cards': fw_cards
    })


@filter_person_cluster
@login_required
@required_role('T')
def ampelmeldung(request):
    from Global.views import check_organization_context
    from ORG.views import _get_ampel_matrix

    freiwillige = _get_Freiwillige(request)
    users = [fw.user for fw in freiwillige]
    ampel_matrix, months = _get_ampel_matrix(request, users)

    context = {
        'ampel_matrix': ampel_matrix,
        'months': months,
        'current_month': timezone.now().strftime("%b %y"),
    }

    context = check_organization_context(request, context)

    return render(request, 'list_ampel.html', context)

    