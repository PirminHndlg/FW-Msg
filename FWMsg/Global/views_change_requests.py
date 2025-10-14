"""
Views for Change Request functionality.
Allows Team and Ehemalige members to request changes to Einsatzland and Einsatzstelle data.
Organization members can review and approve/reject these change requests.
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.urls import reverse
from django.conf import settings

from FWMsg.decorators import required_role
from .models import ChangeRequest, Einsatzland2, Einsatzstelle2
from .send_email import (
    send_email_with_archive,
    format_change_request_new_email,
    format_change_request_decision_email,
    get_logo_base64,
    get_org_color
)
from .push_notification import send_push_notification_to_user
from django.contrib.auth.models import User
import logging

logger = logging.getLogger(__name__)


def _get_team_or_ehemalige_member(request):
    """
    Helper function to get either Team or Ehemalige member for the current user.
    Returns tuple of (member, assigned_countries)
    """
    from TEAM.models import Team
    
    # Check if user is Team member
    team_member = Team.objects.filter(user=request.user).first()
    if team_member:
        return team_member, team_member.land.all()
    
    # For Ehemalige, they can see all countries in their org
    # But you might want to restrict this based on your requirements
    if request.user.customuser.person_cluster.view == 'E':
        assigned_countries = Einsatzland2.objects.filter(org=request.user.org)
        return None, assigned_countries
    
    return None, Einsatzland2.objects.none()


@login_required
@required_role('TE')
def save_einsatzstelle_info(request, stelle_id):
    """Create change request for placement location information."""
    if request.method != 'POST':
        return redirect('einsatzstellen_info')
    
    # Get the member and verify they exist
    member, assigned_countries = _get_team_or_ehemalige_member(request)
    
    if not assigned_countries.exists():
        messages.error(request, 'Sie haben keine Berechtigung, diese Änderungen vorzunehmen.')
        return redirect('einsatzstellen_info')
    
    try:
        # Get the placement location and verify access via country
        stelle = Einsatzstelle2.objects.get(id=stelle_id, org=request.user.org)
        if stelle.land not in assigned_countries:
            messages.error(request, f'Sie haben keine Berechtigung, Informationen für {stelle.name} zu bearbeiten.')
            return redirect('einsatzstellen_info')
        
        # Collect changes
        field_changes = {}
        fields = ['partnerorganisation', 'arbeitsvorgesetzter', 'mentor', 'botschaft', 'konsulat', 'informationen']
        
        for field in fields:
            new_value = request.POST.get(field, '')
            current_value = getattr(stelle, field) or ''
            if new_value != current_value:
                field_changes[field] = new_value
        
        if field_changes:
            # Create change request instead of direct save
            change_request = ChangeRequest.objects.create(
                org=request.user.org,
                change_type='einsatzstelle',
                object_id=stelle.id,
                requested_by=request.user,
                field_changes=field_changes,
                reason=request.POST.get('reason', '')
            )
            
            # Send notification to ORG members
            _notify_org_members_of_change_request(change_request)
            
            messages.success(request, f'Änderungsantrag für {stelle.name} wurde eingereicht und wartet auf Genehmigung.')
        else:
            messages.info(request, 'Keine Änderungen erkannt.')
            
        # Redirect back to einsatzstellen_info view
        return redirect('einsatzstellen_info')
        
    except Einsatzstelle2.DoesNotExist:
        messages.error(request, 'Die angegebene Einsatzstelle wurde nicht gefunden.')
        return redirect('einsatzstellen_info')
    except Exception as e:
        logger.error(f"Error creating change request: {e}")
        messages.error(request, f'Fehler beim Erstellen des Änderungsantrags: {str(e)}')
        return redirect('einsatzstellen_info')


@login_required
@required_role('TE')
def save_land_info(request, land_id):
    """Create change request for country information."""
    if request.method != 'POST':
        return redirect('laender_info')
    
    # Get the member and verify they exist
    member, assigned_countries = _get_team_or_ehemalige_member(request)
    
    if not assigned_countries.exists():
        messages.error(request, 'Sie haben keine Berechtigung, diese Änderungen vorzunehmen.')
        return redirect('laender_info')
    
    try:
        # Get the country and verify access
        land = Einsatzland2.objects.get(id=land_id, org=request.user.org)
        if land not in assigned_countries:
            messages.error(request, f'Sie haben keine Berechtigung, Informationen für {land.name} zu bearbeiten.')
            return redirect('laender_info')
        
        # Collect changes
        field_changes = {}
        fields = ['notfallnummern', 'arztpraxen', 'apotheken', 'informationen']
        
        for field in fields:
            new_value = request.POST.get(field, '')
            current_value = getattr(land, field) or ''
            if new_value != current_value:
                field_changes[field] = new_value
        
        if field_changes:
            # Create change request instead of direct save
            change_request = ChangeRequest.objects.create(
                org=request.user.org,
                change_type='einsatzland',
                object_id=land.id,
                requested_by=request.user,
                field_changes=field_changes,
                reason=request.POST.get('reason', '')
            )
            
            # Send notification to ORG members
            _notify_org_members_of_change_request(change_request)
            
            messages.success(request, f'Änderungsantrag für {land.name} wurde eingereicht und wartet auf Genehmigung.')
        else:
            messages.info(request, 'Keine Änderungen erkannt.')
            
        # Redirect back to laender_info view
        return redirect('laender_info')
    
    except Einsatzland2.DoesNotExist:
        messages.error(request, 'Das angegebene Einsatzland wurde nicht gefunden.')
        return redirect('laender_info')
    except Exception as e:
        logger.error(f"Error creating change request: {e}")
        messages.error(request, f'Fehler beim Erstellen des Änderungsantrags: {str(e)}')
        return redirect('laender_info')




def _notify_org_members_of_change_request(change_request):
    """Send notification to ORG members about new change request."""
    from .tasks import send_change_request_new_email_task
    
    try:
        # Queue Celery tasks for org
        try:
            # Send email notification as Celery task with 5 second delay
            send_change_request_new_email_task.apply_async(
                args=[change_request.id],
                countdown=5
            )
        except Exception as e:
            logger.error(f"Error queuing notification task for org member {change_request.org.id}: {e}")
                
    except Exception as e:
        logger.error(f"Error in _notify_org_members_of_change_request: {e}")


def _notify_requester_of_decision(change_request):
    """Notify the requester about the decision on their change request."""
    from .tasks import send_change_request_decision_email_task
    
    try:
        # Queue Celery task for decision notification with 5 second delay
        send_change_request_decision_email_task.apply_async(
            args=[change_request.id],
            countdown=5
        )
        
    except Exception as e:
        logger.error(f"Error in _notify_requester_of_decision: {e}")

