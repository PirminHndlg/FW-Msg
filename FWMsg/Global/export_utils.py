"""
Export utilities for secure data export functionality.

This module contains functions for securely exporting user data with comprehensive
security measures including input validation, sanitization, rate limiting, and audit logging.
"""

import hashlib
import json
import logging
import re
from datetime import datetime, timedelta

from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.utils import timezone
from django.utils.html import strip_tags
from django.utils.translation import gettext_lazy as _

from .models import (
    Ampel2, 
    Bilder2, 
    BilderGallery2,
    Einsatzstelle2,
    EinsatzstelleNotiz, 
    ProfilUser2,
    UserAttribute, 
    UserAufgaben,
    UserAufgabenZwischenschritte,
    KalenderEvent,
    CustomUser,
    Dokument2,
    Ordner2,
    PersonCluster,
    Notfallkontakt2,
    DokumentColor2,
    Post2,
    PostSurveyAnswer,
    PushSubscription,
    StickyNote
)


def export_user_data_securely(user):
    """
    Export all user data including foreign key relationships as a JSON file.
    
    SECURITY FEATURES:
    - Rate limiting (max 1 export per hour per user)
    - Input validation and sanitization
    - Data filtering to prevent sensitive information leakage
    - Error handling to prevent information disclosure
    - Audit logging for security monitoring
    - Content Security Policy headers
    - Data size limits to prevent DoS attacks
    
    Args:
        user: The authenticated user
        
    Returns:
        HttpResponse: JSON file download response
        
    Raises:
        Exception: If export fails (logged but not exposed to user)
    """
    # SECURITY: Rate limiting - max 1 export per hour per user
    cache_key = f"export_data_rate_limit_{user.id}"
    if cache.get(cache_key):
        raise ValueError(_('Datenexport ist nur einmal pro Stunde möglich. Bitte versuchen Sie es später erneut.'))
    
    # Set rate limit for 1 hour
    cache.set(cache_key, True, 3600)
    
    # SECURITY: Validate user has proper permissions
    if not hasattr(user, 'org') or not user.org:
        raise ValueError(_('Ungültige Benutzerberechtigungen.'))
    
    # SECURITY: Check if user is active
    if not user.is_active:
        raise ValueError(_('Ihr Konto ist deaktiviert.'))
    
    # Initialize export data with security info
    export_data = {
        'export_info': {
            'exported_at': timezone.now().isoformat(),
            'user_id': user.id,
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'date_joined': user.date_joined.isoformat() if user.date_joined else None,
            'last_login': user.last_login.isoformat() if user.last_login else None,
            'export_version': '1.0',
            'data_hash': None,  # Will be set after data collection
        },
        'user_data': {}
    }
    
    # SECURITY: Data collection with error handling and filtering
    export_data['user_data'] = _collect_user_data_securely(user)
    
    # SECURITY: Calculate data hash for integrity
    data_string = json.dumps(export_data, sort_keys=True, ensure_ascii=False)
    export_data['export_info']['data_hash'] = hashlib.sha256(data_string.encode('utf-8')).hexdigest()
    
    # SECURITY: Check data size limit (max 10MB)
    json_data = json.dumps(export_data, indent=2, ensure_ascii=False)
    if len(json_data.encode('utf-8')) > 10 * 1024 * 1024:  # 10MB limit
        raise ValueError(_('Die zu exportierenden Daten sind zu groß. Bitte kontaktieren Sie den Administrator.'))
    
    # SECURITY: Sanitize filename
    safe_username = re.sub(r'[^a-zA-Z0-9_-]', '_', user.username)
    timestamp = timezone.now().strftime("%Y%m%d_%H%M%S")
    filename = f"user_data_{safe_username}_{timestamp}.json"
    
    # Create response with security headers
    response = HttpResponse(json_data, content_type='application/json; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    # SECURITY: Add security headers
    response['X-Content-Type-Options'] = 'nosniff'
    response['X-Frame-Options'] = 'DENY'
    response['X-XSS-Protection'] = '1; mode=block'
    response['Content-Security-Policy'] = "default-src 'none'"
    response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response['Pragma'] = 'no-cache'
    
    # SECURITY: Audit logging
    logger = logging.getLogger('security')
    logger.info(
        f'Data export successful for user {user.id} ({user.username}) - '
        f'File size: {len(json_data)} bytes, Hash: {export_data["export_info"]["data_hash"]}'
    )
    
    return response


def _collect_user_data_securely(user):
    """
    Collect user data with security measures.
    
    Args:
        user: The authenticated user
        
    Returns:
        dict: Sanitized user data
    """
    user_data = {}
    
    try:
        # Get CustomUser data with error handling
        user_data['custom_user'] = _get_custom_user_data(user)
    except Exception as e:
        user_data['custom_user'] = None
        logger = logging.getLogger('security')
        logger.warning(f'Failed to get custom user data for {user.id}: {str(e)}')
    
    try:
        # Get UserAttribute data
        user_attributes = UserAttribute.objects.filter(user=user, org=user.org, attribute__visible_in_profile=True)
        user_data['user_attributes'] = [
            {
                'id': attr.id,
                'attribute_name': _sanitize_text(attr.attribute.name),
                'attribute_type': attr.attribute.type,
                'value': _sanitize_text(attr.value),
            } for attr in user_attributes
        ]
    except Exception as e:
        user_data['user_attributes'] = []
        logger = logging.getLogger('security')
        logger.warning(f'Failed to get user attributes for {user.id}: {str(e)}')
    
    try:
        # Get ProfilUser2 data
        profil_data = ProfilUser2.objects.filter(user=user, org=user.org)
        user_data['profile_data'] = [
            {
                'id': prof.id,
                'attribut': _sanitize_text(prof.attribut),
                'value': _sanitize_text(prof.value),
            } for prof in profil_data
        ]
    except Exception as e:
        user_data['profile_data'] = []
        logger = logging.getLogger('security')
        logger.warning(f'Failed to get profile data for {user.id}: {str(e)}')
    
    try:
        # Get KalenderEvent data (events where user is a participant)
        calendar_events = KalenderEvent.objects.filter(user=user, org=user.org)
        user_data['calendar_events'] = [
            {
                'id': event.id,
                'title': _sanitize_text(event.title),
                'start': event.start.isoformat(),
                'end': event.end.isoformat(),
                'description': _sanitize_text(event.description),
                'mail_reminder_sent': user in event.mail_reminder_sent_to.all(),
            } for event in calendar_events
        ]
    except Exception as e:
        user_data['calendar_events'] = []
        logger = logging.getLogger('security')
        logger.warning(f'Failed to get calendar events for {user.id}: {str(e)}')
    
    try:
        # Get Dokument2 data (documents in folders accessible to user)
        documents = Dokument2.objects.filter(org=user.org, darf_bearbeiten__in=[user.person_cluster]) if user.person_cluster else []
        user_data['documents'] = [
            {
                'id': doc.id,
                'titel': _sanitize_text(doc.titel),
                'beschreibung': _sanitize_text(doc.beschreibung),
                'date_created': doc.date_created.isoformat(),
                'date_modified': doc.date_modified.isoformat(),
                'ordner_name': _sanitize_text(doc.ordner.ordner_name),
                'link': _sanitize_url(doc.link),
            } for doc in documents
        ]
    except Exception as e:
        user_data['documents'] = []
        logger = logging.getLogger('security')
        logger.warning(f'Failed to get documents for {user.id}: {str(e)}')
    
    try:
        # Get Bilder2 data
        images = Bilder2.objects.filter(user=user, org=user.org)
        user_data['images'] = [
            {
                'id': bild.id,
                'titel': _sanitize_text(bild.titel),
                'beschreibung': _sanitize_text(bild.beschreibung),
                'date_created': bild.date_created.isoformat(),
                'date_updated': bild.date_updated.isoformat(),
                'gallery_count': bild.bildergallery2_set.count(),
            } for bild in images
        ]
    except Exception as e:
        user_data['images'] = []
        logger = logging.getLogger('security')
        logger.warning(f'Failed to get images for {user.id}: {str(e)}')
    
    try:
        # Get Post2 data
        posts = Post2.objects.filter(user=user, org=user.org)
        user_data['posts'] = [
            {
                'id': post.id,
                'title': _sanitize_text(post.title),
                'text': _sanitize_text(post.text),
                'date': post.date.isoformat(),
                'date_updated': post.date_updated.isoformat(),
                'has_survey': post.has_survey,
                'person_clusters': [_sanitize_text(pc.name) for pc in post.person_cluster.all()],
            } for post in posts
        ]
    except Exception as e:
        user_data['posts'] = []
        logger = logging.getLogger('security')
        logger.warning(f'Failed to get posts for {user.id}: {str(e)}')
    
    try:
        # Get PostSurveyAnswer data (votes)
        survey_answers = PostSurveyAnswer.objects.filter(votes=user, org=user.org)
        user_data['survey_votes'] = [
            {
                'id': answer.id,
                'question_text': _sanitize_text(answer.question.question_text),
                'answer_text': _sanitize_text(answer.answer_text),
                'post_title': _sanitize_text(answer.question.post.title),
            } for answer in survey_answers
        ]
    except Exception as e:
        user_data['survey_votes'] = []
        logger = logging.getLogger('security')
        logger.warning(f'Failed to get survey votes for {user.id}: {str(e)}')
    
    try:
        # Get Notfallkontakt2 data
        emergency_contacts = Notfallkontakt2.objects.filter(user=user, org=user.org)
        user_data['emergency_contacts'] = [
            {
                'id': contact.id,
                'first_name': _sanitize_text(contact.first_name),
                'last_name': _sanitize_text(contact.last_name),
                'phone_work': _sanitize_phone(contact.phone_work),
                'phone': _sanitize_phone(contact.phone),
                'email': _sanitize_email(contact.email),
            } for contact in emergency_contacts
        ]
    except Exception as e:
        user_data['emergency_contacts'] = []
        logger = logging.getLogger('security')
        logger.warning(f'Failed to get emergency contacts for {user.id}: {str(e)}')
    
    try:
        # Get Ampel2 data
        ampel_status = Ampel2.objects.filter(user=user, org=user.org).order_by('-date')
        user_data['ampel_status'] = [
            {
                'id': ampel.id,
                'status': ampel.status,
                'comment': _sanitize_text(ampel.comment),
                'date': ampel.date.isoformat(),
            } for ampel in ampel_status
        ]
    except Exception as e:
        user_data['ampel_status'] = []
        logger = logging.getLogger('security')
        logger.warning(f'Failed to get ampel status for {user.id}: {str(e)}')
    
    try:
        # Get UserAufgaben data
        user_tasks = UserAufgaben.objects.filter(user=user, org=user.org)
        user_data['tasks'] = [
            {
                'id': task.id,
                'aufgabe_name': _sanitize_text(task.aufgabe.name),
                'aufgabe_beschreibung': _sanitize_text(task.aufgabe.beschreibung),
                'personalised_description': _sanitize_text(task.personalised_description),
                'erledigt': task.erledigt,
                'pending': task.pending,
                'datetime': task.datetime.isoformat(),
                'faellig': task.faellig.isoformat() if task.faellig else None,
                'erledigt_am': task.erledigt_am.isoformat() if task.erledigt_am else None,
                'last_reminder': task.last_reminder.isoformat() if task.last_reminder else None,
                'file_uploaded': bool(task.file),
                'file_count': len(task.file_list) if task.file_list else 0,
                'benachrichtigung_cc': _sanitize_email_list(task.benachrichtigung_cc),
            } for task in user_tasks
        ]
    except Exception as e:
        user_data['tasks'] = []
        logger = logging.getLogger('security')
        logger.warning(f'Failed to get tasks for {user.id}: {str(e)}')
    
    try:
        # Get UserAufgabenZwischenschritte data
        task_steps = UserAufgabenZwischenschritte.objects.filter(user_aufgabe__user=user, org=user.org)
        user_data['task_steps'] = [
            {
                'id': step.id,
                'aufgabe_name': _sanitize_text(step.user_aufgabe.aufgabe.name),
                'step_name': _sanitize_text(step.aufgabe_zwischenschritt.name),
                'step_description': _sanitize_text(step.aufgabe_zwischenschritt.beschreibung),
                'erledigt': step.erledigt,
            } for step in task_steps
        ]
    except Exception as e:
        user_data['task_steps'] = []
        logger = logging.getLogger('security')
        logger.warning(f'Failed to get task steps for {user.id}: {str(e)}')
    
    try:
        # Get PushSubscription data
        push_subscriptions = PushSubscription.objects.filter(user=user, org=user.org)
        user_data['push_subscriptions'] = [
            {
                'id': sub.id,
                'name': _sanitize_text(sub.name),
                'created_at': sub.created_at.isoformat(),
                'last_used': sub.last_used.isoformat() if sub.last_used else None,
            } for sub in push_subscriptions
        ]
    except Exception as e:
        user_data['push_subscriptions'] = []
        logger = logging.getLogger('security')
        logger.warning(f'Failed to get push subscriptions for {user.id}: {str(e)}')
    
    try:
        # Get EinsatzstelleNotiz data
        einsatzstelle_notes = EinsatzstelleNotiz.objects.filter(user=user, org=user.org)
        user_data['einsatzstelle_notes'] = [
            {
                'id': note.id,
                'einsatzstelle_name': _sanitize_text(note.einsatzstelle.name),
                'einsatzstelle_land': _sanitize_text(note.einsatzstelle.land.name if note.einsatzstelle.land else None),
                'notiz': _sanitize_text(note.notiz),
                'date': note.date.isoformat(),
                'pinned': note.pinned,
            } for note in einsatzstelle_notes
        ]
    except Exception as e:
        user_data['einsatzstelle_notes'] = []
        logger = logging.getLogger('security')
        logger.warning(f'Failed to get einsatzstelle notes for {user.id}: {str(e)}')
    
    try:
        # Get StickyNote data
        sticky_notes = StickyNote.objects.filter(user=user, org=user.org)
        user_data['sticky_notes'] = [
            {
                'id': note.id,
                'notiz': _sanitize_text(note.notiz),
                'date': note.date.isoformat(),
                'pinned': note.pinned,
                'priority': note.priority,
            } for note in sticky_notes
        ]
    except Exception as e:
        user_data['sticky_notes'] = []
        logger = logging.getLogger('security')
        logger.warning(f'Failed to get sticky notes for {user.id}: {str(e)}')
    
    return user_data


def _get_custom_user_data(user):
    """Get custom user data with error handling."""
    try:
        custom_user = CustomUser.objects.get(user=user)
        return {
            'id': custom_user.id,
            'person_cluster': {
                'id': custom_user.person_cluster.id,
                'name': _sanitize_text(custom_user.person_cluster.name),
                'view': custom_user.person_cluster.view,
            } if custom_user.person_cluster else None,
            'geburtsdatum': custom_user.geburtsdatum.isoformat() if custom_user.geburtsdatum else None,
            'mail_notifications': custom_user.mail_notifications,
            'date_created': custom_user.history.earliest().history_date.isoformat() if custom_user.history.exists() else None,
        }
    except CustomUser.DoesNotExist:
        return None


def _sanitize_text(text):
    """Sanitize text input to prevent XSS and injection attacks."""
    if not text:
        return text
    
    # Remove HTML tags
    text = strip_tags(str(text))
    
    # Remove potentially dangerous characters
    text = re.sub(r'[<>"\']', '', text)
    
    # Limit length to prevent DoS
    if len(text) > 10000:  # 10KB limit
        text = text[:10000]
    
    return text.strip()


def _sanitize_email(email):
    """Sanitize email address."""
    if not email:
        return email
    
    # Basic email validation
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if re.match(email_pattern, str(email)):
        return str(email).lower().strip()
    
    return None


def _sanitize_email_list(email_list):
    """Sanitize comma-separated email list."""
    if not email_list:
        return email_list
    
    emails = [email.strip() for email in str(email_list).split(',')]
    sanitized_emails = []
    
    for email in emails:
        sanitized_email = _sanitize_email(email)
        if sanitized_email:
            sanitized_emails.append(sanitized_email)
    
    return ', '.join(sanitized_emails) if sanitized_emails else None


def _sanitize_phone(phone):
    """Sanitize phone number."""
    if not phone:
        return phone
    
    # Remove all non-digit characters except +, -, (, ), and space
    phone = re.sub(r'[^\d+\-\(\)\s]', '', str(phone))
    
    # Limit length
    if len(phone) > 20:
        phone = phone[:20]
    
    return phone.strip()


def _sanitize_url(url):
    """Sanitize URL."""
    if not url:
        return url
    
    url = str(url).strip()
    
    # Basic URL validation
    url_pattern = r'^https?://[^\s/$.?#].[^\s]*$'
    if re.match(url_pattern, url):
        return url
    
    return None 