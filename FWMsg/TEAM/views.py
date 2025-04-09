from django.utils import timezone
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from Global.models import Einsatzland2, Freiwilliger2, Referenten2, Einsatzstelle2, Ampel2, UserAttribute
from django.contrib import messages

from ORG.views import filter_person_cluster, _get_ampel_matrix
from FWMsg.decorators import required_role
base_template = 'baseTeam.html'

# Create your views here.
@login_required
@required_role('T')
def home(request):
    return render(request, 'teamHome.html')

def _get_team_member(request):
    """Helper function to get the team member record for the current user."""
    return Referenten2.objects.filter(user=request.user).first()

def _get_Freiwillige(request):
    """Get all volunteers that are assigned to countries this team member manages."""
    team_member = _get_team_member(request)
    if team_member:
        countries = team_member.land.all()
        return Freiwilliger2.objects.filter(einsatzland__in=countries)
    return []

@filter_person_cluster
@login_required
@required_role('T')
def contacts(request):
    # Get freiwillige with prefetched user data to reduce queries
    freiwillige = _get_Freiwillige(request).select_related('user')
    
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

@filter_person_cluster
@login_required
@required_role('T')
def einsatzstellen(request):
    """View for team members to manage their assigned placement locations."""
    # Get the team member's assigned countries
    team_member = _get_team_member(request)
    
    if not team_member:
        messages.warning(request, 'Ihrem Konto sind keine Einsatzländer zugeordnet. Bitte kontaktieren Sie den Administrator.')
        return render(request, 'teamEinsatzstellen.html', {'einsatzstellen': []})
    
    # Get placement locations for assigned countries
    einsatzstellen = Einsatzstelle2.objects.filter(land__in=team_member.land.all()).order_by('name')
    
    # Check if there are any placement locations
    if not einsatzstellen.exists():
        messages.info(request, 'Es wurden keine Einsatzstellen in Ihren zugewiesenen Ländern gefunden.')
    
    # Process success message from query parameters
    saved_id = request.GET.get('saved')
    if saved_id:
        try:
            saved_stelle = einsatzstellen.get(id=saved_id)
            messages.success(request, f'Die Informationen für {saved_stelle.name} wurden erfolgreich gespeichert.')
        except Einsatzstelle2.DoesNotExist:
            pass  # Ignore if the placement location doesn't exist
    
    return render(request, 'teamEinsatzstellen.html', {'einsatzstellen': einsatzstellen})

@filter_person_cluster
@login_required
@required_role('T')
def save_einsatzstelle_info(request, stelle_id):
    """Save updated placement location information from the team interface."""
    if request.method != 'POST':
        return redirect('einsatzstellen')
    
    # Get the team member and verify they exist
    team_member = _get_team_member(request)
    if not team_member:
        messages.error(request, 'Sie haben keine Berechtigung, diese Änderungen vorzunehmen.')
        return redirect('einsatzstellen')
    
    # Get assigned countries
    assigned_countries = team_member.land.all()
    
    try:
        # Get the placement location and verify the team member has access to it via country
        stelle = Einsatzstelle2.objects.get(id=stelle_id)
        if stelle.land not in assigned_countries:
            messages.error(request, f'Sie haben keine Berechtigung, Informationen für {stelle.name} zu bearbeiten.')
            return redirect('einsatzstellen')
        
        # Update the placement location information with form data
        stelle.partnerorganisation = request.POST.get('partnerorganisation', '')
        stelle.arbeitsvorgesetzter = request.POST.get('arbeitsvorgesetzter', '')
        stelle.mentor = request.POST.get('mentor', '')
        stelle.botschaft = request.POST.get('botschaft', '')
        stelle.konsulat = request.POST.get('konsulat', '')
        stelle.informationen = request.POST.get('informationen', '')
        stelle.save()
        
        # Redirect with success parameter that includes the ID
        return redirect(f'/team/einsatzstellen/?saved={stelle.id}')
    
    except Einsatzstelle2.DoesNotExist:
        messages.error(request, 'Die angegebene Einsatzstelle wurde nicht gefunden.')
        return redirect('einsatzstellen')
    except Exception as e:
        messages.error(request, f'Fehler beim Speichern der Informationen: {str(e)}')
        return redirect('einsatzstellen')

@filter_person_cluster
@login_required
@required_role('T')
def laender(request):
    """View for team members to manage their assigned countries' information."""
    # Get the team member's assigned countries
    team_member = _get_team_member(request)
    
    if not team_member:
        messages.warning(request, 'Ihrem Konto sind keine Einsatzländer zugeordnet. Bitte kontaktieren Sie den Administrator.')
        return render(request, 'teamLaender.html', {'laender': []})
    
    # Get assigned countries with prefetch for better performance
    laender = team_member.land.all().order_by('name')
    
    # Check if there are any countries assigned
    if not laender.exists():
        messages.info(request, 'Ihrem Konto sind derzeit keine Einsatzländer zugeordnet.')
    
    # Process success message from query parameters
    saved_id = request.GET.get('saved')
    if saved_id:
        try:
            saved_land = laender.get(id=saved_id)
            messages.success(request, f'Die Informationen für {saved_land.name} wurden erfolgreich gespeichert.')
        except Einsatzland2.DoesNotExist:
            pass  # Ignore if the country doesn't exist
    
    return render(request, 'teamLaender.html', {'laender': laender})

@filter_person_cluster
@login_required
@required_role('T')
def save_land_info(request, land_id):
    """Save updated country information from the team interface."""
    if request.method != 'POST':
        return redirect('laender')
    
    # Get the team member and verify they exist
    team_member = _get_team_member(request)
    if not team_member:
        messages.error(request, 'Sie haben keine Berechtigung, diese Änderungen vorzunehmen.')
        return redirect('laender')
    
    # Get assigned countries
    assigned_countries = team_member.land.all()
    
    try:
        # Get the country and verify the team member has access to it
        land = Einsatzland2.objects.get(id=land_id)
        if land not in assigned_countries:
            messages.error(request, f'Sie haben keine Berechtigung, Informationen für {land.name} zu bearbeiten.')
            return redirect('laender')
        
        # Update the country information with form data
        land.notfallnummern = request.POST.get('notfallnummern', '')
        land.arztpraxen = request.POST.get('arztpraxen', '')
        land.apotheken = request.POST.get('apotheken', '')
        land.informationen = request.POST.get('informationen', '')
        land.save()
        
        # Redirect with success parameter that includes the ID
        return redirect(f'/team/laender/?saved={land.id}')
    
    except Einsatzland2.DoesNotExist:
        messages.error(request, 'Das angegebene Einsatzland wurde nicht gefunden.')
        return redirect('laender')
    except Exception as e:
        messages.error(request, f'Fehler beim Speichern der Informationen: {str(e)}')
        return redirect('laender')
    
    