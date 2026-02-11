from datetime import date, datetime
import io
import os
import zipfile
from django.urls import reverse
import pandas as pd
import json

from django.db.models import ForeignKey
from django.shortcuts import render, redirect
from django.http import HttpResponse, HttpResponseNotAllowed, HttpResponseNotFound, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from functools import wraps
from django.utils import timezone
from django.db.models import QuerySet, Subquery, OuterRef
from django.db.models import Count, Q
from django.contrib.admin.views.decorators import staff_member_required
from django.template.loader import render_to_string
from django.db.models.query import Prefetch
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.utils.translation import gettext as _

from BW.models import ApplicationAnswer, ApplicationAnswerFile, ApplicationText, ApplicationQuestion, ApplicationFileQuestion, Bewerber
from Ehemalige.models import Ehemalige
from Global.models import (
    Attribute, AufgabenCluster, Aufgabe2, KalenderEvent, Maintenance, PersonCluster, StickyNote, UserAttribute, 
    UserAufgaben, Post2, Bilder2, CustomUser,
    BilderGallery2, Ampel2, ProfilUser2, Notfallkontakt2,
    Einsatzland2, Einsatzstelle2,
    AufgabeZwischenschritte2, UserAufgabenZwischenschritte,
    EinsatzstelleNotiz, ChangeRequest
)
from TEAM.models import Team
from FW.models import Freiwilliger
from django.contrib.auth.models import User

import ORG.forms as ORGforms
from FWMsg.decorators import required_role
from django.views.decorators.http import require_http_methods
from .pdf_utils import (
    generate_full_application_pdf, 
    generate_selected_application_pdf, 
    create_pdf_response
)

base_template = 'baseOrg.html'

def get_person_cluster(request):
    person_cluster_id = request.COOKIES.get('selectedPersonCluster')
    if person_cluster_id and not PersonCluster.objects.filter(id=person_cluster_id, org=request.user.org).exists():
        person_cluster_id = None
        response = HttpResponseRedirect(request.META.get('HTTP_REFERER', '/'))
        if 'selectedPersonCluster' in request.COOKIES:
            response.delete_cookie('selectedPersonCluster')
        if 'selectedPersonClusterName' in request.COOKIES:
            response.delete_cookie('selectedPersonClusterName')
        return response
    else:
        return None
        # return PersonCluster.objects.get(id=person_cluster_id) if person_cluster_id else None

@login_required
@required_role('O')
@require_http_methods(["GET"])
def ajax_einsatzstellen_by_land(request):
    """Return Einsatzstelle2 options filtered by einsatzland2 for the current org.

    Query params:
    - land_id: int (Einsatzland2 id)

    Response: JSON list of {id, name}
    """
    try:
        land_id = request.GET.get('land_id')
        if not land_id or not str(land_id).isdigit():
            return JsonResponse({'error': 'Invalid or missing land_id'}, status=400)

        stellen = Einsatzstelle2.objects.filter(org=request.user.org, land_id=int(land_id)).order_by('name')
        data = [{'id': s.id, 'name': s.name} for s in stellen]
        return JsonResponse({'results': data})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def get_filtered_user_queryset(request, requested_view=None):
    view_filter_map = {
            'aufgaben': 'aufgaben',
            'calendar': 'calendar', 
            'dokumente': 'dokumente',
            'ampel': 'ampel',
            'notfallkontakt': 'notfallkontakt',
            'bilder': 'bilder'
        }
    
    base_filter = {
        'customuser__org': request.user.org,
        'customuser__person_cluster__isnull': False
    }

    if requested_view and requested_view in view_filter_map:
        base_filter[f'customuser__person_cluster__{view_filter_map[requested_view]}'] = True
    
    person_cluster = get_person_cluster(request)
    if person_cluster:
        base_filter['customuser__person_cluster'] = person_cluster
        
    return User.objects.filter(**base_filter).order_by('-customuser__person_cluster', 'first_name', 'last_name'), person_cluster


def org_context_processor(request):
    """Context processor to add jahrgaenge to all templates."""
    if hasattr(request, 'user') and request.user.is_authenticated:
        if request.user.role == 'O':
            return {
                'person_cluster': PersonCluster.objects.filter(org=request.user.org)
            }
        elif request.user.role == 'T':
            return {
                'person_cluster': PersonCluster.objects.filter(org=request.user.org, view='F')
            }
    return {}

allowed_models_to_edit = {
    'einsatzland': Einsatzland2,
    'einsatzstelle': Einsatzstelle2,
    'freiwilliger': Freiwilliger,
    'bewerber': Bewerber,
    'attribute': Attribute,
    'aufgabe': Aufgabe2,
    'notfallkontakt': Notfallkontakt2,
    'ehemalige': Ehemalige,
    'useraufgaben': UserAufgaben,
    'team': Team,
    'user': CustomUser,
    'personcluster': PersonCluster,
    'aufg-filter': AufgabenCluster,
    'kalender': KalenderEvent,
    'bewerbung-text': ApplicationText,
    'bewerbung-frage': ApplicationQuestion,
    'bewerbung-datei': ApplicationFileQuestion,
}


# Create your views here.
@login_required
@required_role('O')
def home(request):
    from Global.views import get_bilder, get_posts

    # Get all gallery images and group by bilder
    gallery_images = get_bilder(request.user.org, limit=6)

    # Get pending tasks
    now = timezone.now().date()
    pending_tasks = UserAufgaben.objects.filter(
        org=request.user.org,
        erledigt=False,
        pending=True,
    ).order_by('-erledigt_am', 'faellig')  # Order by deadline

    open_tasks = UserAufgaben.objects.filter(
        org=request.user.org,
        erledigt=False,
        pending=False,
        faellig__lte=now
    ).order_by('faellig')

    my_open_tasks = UserAufgaben.objects.filter(
        org=request.user.org,
        user=request.user,
        erledigt=False,
        pending=False
    ).order_by('faellig')

    posts = get_posts(request.user.org, limit=4)

    # Get all pinned notes across all Einsatzstellen
    pinned_notizen = EinsatzstelleNotiz.objects.filter(
        org=request.user.org,
        pinned=True
    ).order_by('-date')
    
    sticky_notes = StickyNote.objects.filter(
        org=request.user.org,
        user=request.user,
        pinned=True
    ).order_by('-priority', '-date')

    # Get recent ampel entries
    recent_ampel_entries = Ampel2.objects.filter(
        org=request.user.org,
        date__gte=timezone.now() - timezone.timedelta(days=5)
    ).select_related('user').order_by('-date')[:10]

    context = {
        'gallery_images': gallery_images,
        'pending_tasks': pending_tasks,
        'open_tasks': open_tasks,
        'my_open_tasks': my_open_tasks,
        'posts': posts,
        'pinned_notizen': pinned_notizen,
        'sticky_notes': sticky_notes,
        'recent_ampel_entries': recent_ampel_entries,
        'large_container': True,
        'today': date.today()
    }   
    
    return render(request, 'homeOrg.html', context=context)


@login_required
@required_role('O')
def home_2(request):
    from Global.views import get_bilder, get_posts

    # Get all gallery images and group by bilder
    gallery_images = get_bilder(request.user.org, limit=4)

    # Get pending tasks
    now = timezone.now().date()
    pending_tasks = UserAufgaben.objects.filter(
        org=request.user.org,
        erledigt=False,
        pending=True,
    ).order_by('-erledigt_am', 'faellig')  # Order by deadline

    open_tasks = UserAufgaben.objects.filter(
        org=request.user.org,
        erledigt=False,
        pending=False,
        faellig__lte=now
    ).order_by('faellig')

    my_open_tasks = UserAufgaben.objects.filter(
        org=request.user.org,
        user=request.user,
        erledigt=False,
        pending=False
    ).order_by('faellig')

    posts = get_posts(request.user.org, limit=4)

    # Get all pinned notes across all Einsatzstellen
    pinned_notizen = EinsatzstelleNotiz.objects.filter(
        org=request.user.org,
        pinned=True
    ).order_by('-date')
    
    sticky_notes = StickyNote.objects.filter(
        org=request.user.org,
        user=request.user,
        pinned=True
    ).order_by('-priority', '-date')

    # Get recent ampel entries
    recent_ampel_entries = Ampel2.objects.filter(
        org=request.user.org,
        date__gte=timezone.now() - timezone.timedelta(days=5)
    ).select_related('user').order_by('-date')[:10]

    # Get pending change requests
    pending_change_requests = ChangeRequest.objects.filter(
        org=request.user.org,
        status='pending'
    ).select_related('requested_by').order_by('-created_at')

    context = {
        'gallery_images': gallery_images,
        'pending_tasks': pending_tasks,
        'open_tasks': open_tasks,
        'my_open_tasks': my_open_tasks,
        'posts': posts,
        'pinned_notizen': pinned_notizen,
        'sticky_notes': sticky_notes,
        'recent_ampel_entries': recent_ampel_entries,
        'pending_change_requests': pending_change_requests,
        'large_container': True,
        'today': date.today()
    }
    
    return render(request, 'homeOrg_2.html', context=context)


@staff_member_required
def nginx_statistic(request):
    try:
        # Path to the pre-generated HTML file
        report_path = '/home/fwmsg/tmp/report.html'
        
        # Read the HTML file with error handling for encoding issues
        try:
            with open(report_path, 'r', encoding='utf-8') as file:
                html_content = file.read()
        except UnicodeDecodeError:
            # Try with a different encoding or fallback to latin-1 which rarely fails
            with open(report_path, 'r', encoding='latin-1') as file:
                html_content = file.read()
            
        # Return the HTML content directly
        return HttpResponse(html_content, content_type='text/html')
        
    except FileNotFoundError:
        return render(request, 'nginx_statistic.html', {
            'error': 'Report file not found. The report may not have been generated yet.'
        })
    except Exception as e:
        return render(request, 'nginx_statistic.html', {
            'error': f"Error reading report: {str(e)}"
        })


@login_required
@required_role('O')
def save_form(request, form):
    """
    Save a form with proper organization assignment and handle related forms.
    
    Args:
        request: The HTTP request object
        form: The form to save
        
    Returns:
        The saved form instance
    """
    # First save without committing to add organization
    obj = form.save(commit=False)
    obj.org = request.user.org
    obj.save()
    
    # Save many-to-many relationships
    form.save_m2m()
    
    # Handle nested zwischenschritte forms if they exist
    if hasattr(form, 'zwischenschritte'):
        for zwischenschritt_form in form.zwischenschritte.forms:
            # Only save non-deleted forms with data
            if (zwischenschritt_form.cleaned_data and 
                not zwischenschritt_form.cleaned_data.get('DELETE', False)):
                # Add organization to each zwischenschritt
                zwischenschritt = zwischenschritt_form.save(commit=False)
                zwischenschritt.org = request.user.org
                zwischenschritt.save()
    
    # Final save to ensure everything is committed
    return form.save(commit=True)


@login_required
@required_role('O')
def add_object(request, model_name):
    freiwilliger_id = request.GET.get('freiwilliger')
    aufgabe_id = request.GET.get('aufgabe')
    
    if freiwilliger_id and aufgabe_id:
        # Get freiwilliger and aufgabe objects and check organization
        freiwilliger, response = _get_object_with_org_check(Freiwilliger, freiwilliger_id, request)
        if response:
            return response
            
        aufgabe, response = _get_object_with_org_check(Aufgabe2, aufgabe_id, request)
        if response:
            return response

        obj, created = UserAufgaben.objects.get_or_create(
            org=request.user.org,
            freiwilliger=freiwilliger,
            aufgabe=aufgabe
        )
        return edit_object(request, model_name, obj.id)
    
    return edit_object(request, model_name, None)

@login_required
@required_role('O')
def add_aufgabe(request, id=None):
    # Get instance if ID is provided and check organization
    instance = None
    if id is not None:
        instance, response = _get_object_with_org_check(Aufgabe2, id, request)
        if response:
            return response

    if request.method == 'POST':
        form = ORGforms.AddAufgabeForm(request.POST, request.FILES, instance=instance, request=request)
        if form.is_valid():
            save_form(request, form)
            next_url = request.GET.get('next')
            if next_url:
                return redirect(next_url)
            # Use the helper function for redirection
            return _redirect_after_action(request, 'aufgabe', form.instance.id)
        else:
            if instance:
                messages.error(request, 'Fehler beim Bearbeiten der Aufgabe. Bitte überprüfe die Eingaben.')
            else:
                messages.error(request, 'Fehler beim Erstellen der Aufgabe. Bitte überprüfe die Eingaben.')
            print("Form errors:", form.errors)
            print("Non-field errors:", form.non_field_errors())
            if hasattr(form, 'zwischenschritte'):
                print("Zwischenschritte errors:", form.zwischenschritte.errors)
            return render(request, 'add_aufgabe.html', {'form': form})
    
    form = ORGforms.AddAufgabeForm(instance=instance, request=request)
    back_url = reverse('list_aufgaben_table')
    return render(request, 'add_aufgabe.html', {'form': form, 'back_url': back_url})

@login_required
@required_role('O')
def add_objects_from_excel(request, model_name):
    if request.method == 'POST':
        excel_file = request.FILES['excel_file']
        df = pd.read_excel(excel_file)
        model, response = _check_model_exists(model_name)
        if response:
            return response

        personen_cluster_id = request.COOKIES.get('selectedPersonCluster')
        if PersonCluster.objects.filter(id=personen_cluster_id).exists():
            personen_cluster = PersonCluster.objects.get(id=personen_cluster_id)
            if personen_cluster.org != request.user.org:
                return HttpResponse(b'Nicht erlaubt')
        else:
            personen_cluster = None

        for index, row in df.iterrows():
            required_fields = []
            for field in model._meta.fields:
                if field.name in row:
                    required_fields.append(field.name)
            print(required_fields)
            try:
                obj = model.objects.create(
                    org=request.user.org,
                    **{field: row[field] for field in required_fields}
                )
                if 'personen_cluster' in model._meta.fields and personen_cluster:
                    obj.personen_cluster = personen_cluster
                for field in model._meta.fields:
                    if field.name in row:
                        setattr(obj, field.name, row[field.name])
                obj.save()
            except Exception as e:
                print(e)
                continue

        return redirect('list_object', model_name=model_name)
    return render(request, 'add_objects_from_excel.html')


@login_required
@required_role('O')
def delete_zwischenschritt(request):
    zwischenschritt_id = request.POST.get('zwischenschritt_id')
    zwischenschritt = AufgabeZwischenschritte2.objects.get(id=zwischenschritt_id)
    zwischenschritt.delete()
    return redirect('edit_object', model_name='aufgabe', id=zwischenschritt.aufgabe.id)


@login_required
@required_role('O')
def toggle_zwischenschritt_status(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        data = json.loads(request.body)
        task_id = data.get('taskId')
        zwischenschritt_id = data.get('zwischenschrittId')
        new_status = data.get('status')
        
        # Get the FreiwilligerAufgabenZwischenschritte instance
        user_aufgabe = UserAufgaben.objects.get(id=task_id)
        zwischenschritt = get_object_or_404(
            UserAufgabenZwischenschritte,
            id=zwischenschritt_id,
            user_aufgabe=user_aufgabe
        )
        
        # Update the status
        zwischenschritt.erledigt = new_status
        zwischenschritt.save()

        user_aufgabe = UserAufgaben.objects.get(id=task_id)
        zwischenschritte = UserAufgabenZwischenschritte.objects.filter(user_aufgabe=user_aufgabe)
        zwischenschritte_count = zwischenschritte.count()
        zwischenschritte_done_count = zwischenschritte.filter(erledigt=True).count()
        json_response = {
            'zwischenschritte_done_open': f'Pending {zwischenschritte_done_count}/{zwischenschritte_count}' if zwischenschritte_count > 0 else False,
            'zwischenschritte_done': zwischenschritte_done_count == zwischenschritte_count and zwischenschritte_count > 0,
            'success': True
        }
        
        return JsonResponse(json_response)
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        print(e)
        return JsonResponse({'error': str(e)}, status=500)

@login_required
@required_role('O')
def get_zwischenschritt_form(request):
    if request.method != 'GET':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        form_html = render_to_string('components/zwischenschritt_form.html')
        return JsonResponse({'html': form_html})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@required_role('O')
def edit_object(request, model_name, id):
    # Redirect aufgabe edits to the specialized add_aufgabe view
    if model_name.lower() == 'aufgabe':
        return add_aufgabe(request, id)
    
    # Check if model exists and has a form mapping
    model, response = _check_model_exists(model_name.lower())
    if response:
        return response
    
    if not model in ORGforms.model_to_form_mapping:
        return HttpResponse(f'Kein Formular für {model_name}')

    # Get instance if ID is provided and check organization
    instance = None
    if id is not None:
        instance, response = _get_object_with_org_check(model, id, request)
        if response:
            return response

    if instance:
        form = ORGforms.model_to_form_mapping[model](
            request.POST or None,
            request.FILES or None,
            instance=instance,
            request=request
        )
    else:
        form = ORGforms.model_to_form_mapping[model](
            request.POST or None,
            request.FILES or None,
            request=request
        )

    if form.is_valid():
        save_form(request, form)
        obj_id = form.instance.id
        
        # Use the helper function for redirection
        return _redirect_after_action(request, model_name, obj_id)

    if form.fields:
        try:
            first_field_name = next(iter(form.fields))
            form.fields[first_field_name].widget.attrs['autofocus'] = True
        except StopIteration:
            pass
        
    if model_name == 'aufgabe':
        back_url = reverse('list_aufgaben_table')
    else:
        back_url = reverse('list_object', args=[model_name])

    return render(request, 'edit_object.html', {'form': form, 'object': model_name, 'verbose_name': model._meta.verbose_name, 'back_url': back_url})


@login_required
@required_role('O')
def list_object(request, model_name, highlight_id=None):
    # Check if model exists using the helper function
    model, response = _check_model_exists(model_name)
    if response:
        return response
    
    # Use djangotables2 for other models
    return _list_object_with_tables2(request, model_name, model, highlight_id)


def _list_object_with_tables2(request, model_name, model, highlight_id=None):
    """New implementation using djangotables2"""
    from django_tables2 import RequestConfig
    from .tables import MODEL_TABLE_MAPPING, get_bewerber_table_class, get_freiwilliger_table_class, get_team_table_class, get_ehemalige_table_class
    
    def set_cookie_for_filter(response, filter):
        if filter['has_active_filter']:
            all_options = filter['options']
            active_option = [option for option in all_options if option['is_active']]
            if active_option:
                response.set_cookie(filter['cookie_name'], active_option[0]['value'])
            else:
                response.delete_cookie(filter['cookie_name'])
        else:
            response.delete_cookie(filter['cookie_name'])
        return response
    
    if model_name.lower() in ['bewerber', 'freiwilliger', 'team', 'ehemalige']:
        checkbox_submit_texts = [choice for choice in model.CHECKBOX_ACTION_CHOICES] if hasattr(model, 'CHECKBOX_ACTION_CHOICES') else []
        
        if model_name.lower() == 'freiwilliger':
            table_class, data, filter_options = get_freiwilliger_table_class(request.user.org, request)
        elif model_name.lower() == 'team':
            table_class, data, filter_options = get_team_table_class(request.user.org, request)
        elif model_name.lower() == 'ehemalige':
            table_class, data, filter_options = get_ehemalige_table_class(request.user.org, request)
        else:
            table_class, data, filter_options = get_bewerber_table_class(request.user.org, request)
            
        # Apply search filter
        search_query = request.GET.get('search', '').strip()
        if search_query:
            search_lower = search_query.lower()
            # search in every field of the data
            for d in data:
                print(d)
            # print accessors of table_class
            print(table_class.base_columns.keys())
            
            # Helper function to extract searchable text from any value
            def get_searchable_text(value):
                """Extract all searchable text from a value, handling special cases."""
                texts = []
                
                if isinstance(value, dict):
                    # Extract all values from dict (e.g., attributes)
                    texts.extend(str(v) for v in value.values())
                elif isinstance(value, (str, int, float)):
                    # Simple values
                    texts.append(str(value))
                elif hasattr(value, '__class__') and hasattr(value.__class__, '__name__'):
                    # It's an object - extract from table columns
                    for column_name in table_class.base_columns.keys():
                        try:
                            attr = getattr(value, column_name, None)
                            if attr is None:
                                continue
                            
                            # Skip file fields (FileField, ImageField)
                            if hasattr(attr, 'url') and hasattr(attr, 'path'):
                                continue
                            
                            # ManyToMany or ForeignKey with .all()
                            if hasattr(attr, 'all') and callable(attr.all):
                                texts.extend(str(obj) for obj in attr.all())
                            # Callable method
                            elif callable(attr):
                                try:
                                    texts.append(str(attr()))
                                except:
                                    pass
                            # Regular attribute
                            else:
                                texts.append(str(attr))
                        except:
                            pass
                
                return ' '.join(texts).lower()
            
            # Search and filter data
            new_data = []
            for row in data:
                # Get all searchable text from all values in the row
                searchable_text = ' '.join(get_searchable_text(v) for v in row.values())
                
                # Check if search query is in the searchable text
                if search_lower in searchable_text:
                    # print(f"Match found for '{search_query}' in:", row.get('user_sort', row))
                    # print(f"Searchable text: {searchable_text[:200]}...")  # Print first 200 chars
                    new_data.append(row)
            
            data = new_data
        
        # Sort data by default if no sort parameter is provided
        if not request.GET.get('sort'):
            data = sorted(data, key=lambda x: x.get('user_sort', ''))
        
        # Generate dynamic table with attribute columns
        total_objects_count = len(data)
        
        # Create table and configure pagination/sorting
        table = table_class(data)
        RequestConfig(request).configure(table)
        
        # Check if any filter is active
        has_active_filters = any(f.get('has_active_filter', False) for f in filter_options) if filter_options else False
        
        response = render(request, 'list_objects_table.html', {
            'table': table,
            'model_name': model_name,
            'verbose_name': model._meta.verbose_name_plural,
            'highlight_id': highlight_id,
            'error': None,
            'total_count': total_objects_count,
            'search_query': search_query,
            'large_container': True,
            'checkbox_submit_texts': checkbox_submit_texts,
            'filter_options': filter_options,
            'has_active_filters': has_active_filters
        })
        
        for filter in filter_options:
            response = set_cookie_for_filter(response, filter)
            
        return response
    
    # Get base queryset with organization filter
    objects = model.objects.filter(org=request.user.org)
    
    # Get field metadata and model fields for model-specific logic
    field_metadata, model_fields = _get_field_metadata(model)
    
    # Apply model-specific logic
    objects = _apply_model_specific_logic(model, objects, field_metadata, model_fields)
    
    # Build filter options (can contain multiple filter groups)
    filter_options = []

    if model_name.lower() == 'user':
        from .tables import get_customuser_filter
        objects, user_filters = get_customuser_filter(request, request.user.org, objects)
        filter_options.extend(user_filters)
    elif model_name.lower() == 'attribute':
        from .tables import build_person_cluster_filter
        pc_filter, selected_cluster = build_person_cluster_filter(
            request, request.user.org, view=None, min_clusters=2
        )
        if pc_filter:
            filter_options.append(pc_filter)
            if selected_cluster:
                objects = objects.filter(person_cluster=selected_cluster).distinct()

    # Count total objects before search filtering
    total_objects_count = objects.count()
    
    # Apply search filter if provided
    search_query = request.GET.get('search', '').strip()
    if search_query:
        objects = _apply_search_filter(objects, model, search_query)
    
    # Get the appropriate table class
    table_class = MODEL_TABLE_MAPPING.get(model_name.lower())
    
    if table_class is None:
        return render(request, 'list_objects_table.html', {
            'error': _('Table not found for model: {}').format(model_name),
            'model_name': model_name,
            'verbose_name': model._meta.verbose_name_plural,
        })
    
    # Create table instance
    table = table_class(objects, model_name=model_name.lower())

    # Configure pagination and sorting
    RequestConfig(request).configure(table)
    
    # Check if any filter is active
    has_active_filters = any(f.get('has_active_filter', False) for f in filter_options) if filter_options else False

    response = render(request, 'list_objects_table.html', {
        'table': table,
        'model_name': model_name,
        'verbose_name': model._meta.verbose_name_plural,
        'highlight_id': highlight_id,
        'total_count': total_objects_count,
        'search_query': search_query,
        'large_container': True,
        'filter_options': filter_options,
        'has_active_filters': has_active_filters
    })

    # Set cookies for filters
    for filter in filter_options:
        response = set_cookie_for_filter(response, filter)
    
    return response

def _apply_search_filter(queryset, model, search_query):
    """Apply search filter to queryset based on searchable fields"""
    from django.db.models import Q
    
    # Get text fields that can be searched
    searchable_fields = []
    for field in model._meta.fields:
        if field.get_internal_type() in ['CharField', 'TextField', 'EmailField']:
            searchable_fields.append(field.name)
    
    # Build search query
    if searchable_fields and search_query:
        search_q = Q()
        for field_name in searchable_fields:
            search_q |= Q(**{f"{field_name}__icontains": search_query})
        
        # Also search in related fields for common patterns
        if hasattr(model, 'user'):
            search_q |= Q(user__first_name__icontains=search_query)
            search_q |= Q(user__last_name__icontains=search_query)
            search_q |= Q(user__username__icontains=search_query)
            search_q |= Q(user__email__icontains=search_query)
        
        queryset = queryset.filter(search_q)
    
    return queryset


def _check_person_cluster_permissions(model, person_cluster):
    """Check if the person cluster has the required permissions for the model."""
    if not person_cluster:
        return None
        
    model_name = model._meta.object_name
    if model_name == 'Aufgabe' and not person_cluster.aufgaben:
        return f'{person_cluster.name} hat keine Aufgaben-Funktion aktiviert'
    elif model_name == 'Notfallkontakt' and not person_cluster.notfallkontakt:
        return f'{person_cluster.name} hat keine Notfallkontakt-Funktion aktiviert'
    elif model_name == 'Freiwilliger' and not person_cluster.view == 'F':
        return f'{person_cluster.name} sind keine Freiwillige'
    elif model_name == 'Team' and not person_cluster.view == 'T':
        return f'{person_cluster.name} sind keine Teammitglieder'
    
    return None

def _get_field_metadata(model):
    """Get field metadata and model fields."""
    field_metadata = [
        {'name': field.name, 'verbose_name': field.verbose_name}
        for field in model._meta.fields if field.name not in ['org', 'id']
    ]
    
    model_fields = [field.name for field in model._meta.fields]
    
    return field_metadata, model_fields

def _get_m2m_fields(model):
    """Get many-to-many fields metadata."""
    return [
        {'name': field.name, 'verbose_name': field.verbose_name}
        for field in model._meta.many_to_many
    ]

def _apply_model_specific_logic(model, objects, field_metadata, model_fields):
    """Apply model-specific logic to the queryset."""
    model_name = model._meta.object_name
    
    # Common user fields
    user_fields = [
        {'name': 'user_first_name', 'verbose_name': 'Vorname', 'type': 'T'},
        {'name': 'user_last_name', 'verbose_name': 'Nachname', 'type': 'T'},
        {'name': 'user_email', 'verbose_name': 'Email', 'type': 'E'}
    ]
    
    objects = _handle_default_model(objects, model_fields)
    
    return objects


def _handle_default_model(objects, model_fields):
    """Handle default model ordering logic."""
    if 'freiwilliger' in model_fields:
        objects = objects.order_by('freiwilliger__first_name', 'freiwilliger__last_name')
    elif 'first_name' in model_fields:
        objects = objects.order_by('first_name')
    elif 'last_name' in model_fields:
        objects = objects.order_by('last_name')
    elif 'name' in model_fields:
        objects = objects.order_by('name')
    return objects

def _apply_pagination(objects, request):
    """Apply pagination to the queryset."""
    page = request.GET.get('page', 1)
    items_per_page = 50
    paginator = Paginator(objects, items_per_page)
    
    try:
        paginated_objects = paginator.page(page)
    except PageNotAnInteger:
        paginated_objects = paginator.page(1)
    except EmptyPage:
        paginated_objects = paginator.page(paginator.num_pages)
    
    # Create query parameters for pagination links
    query_params = request.GET.copy()
    if 'page' in query_params:
        del query_params['page']
    query_string = query_params.urlencode()
    
    return paginated_objects, query_string


@login_required
@required_role('O')
def list_object_checkbox(request, model_name):
    model, response = _check_model_exists(model_name)
    if response:
        return response
    
    objects = request.GET.getlist('checkbox')
    if objects:
        counter = 0
        for object_id in objects:
            instance, response = _get_object_with_org_check(model, int(object_id), request)
            if response:
                return response
            # do something with the object
            checkbox_submit_value = request.GET.get('checkbox_submit_value')
            if hasattr(instance, 'checkbox_action') and not instance.checkbox_action(request.user.org, checkbox_submit_value):
                messages.error(request, _('Aktion für {instance} nicht erfolgreich durchgeführt.').format(instance=instance))
            else:
                counter += 1
        
        object_name = model._meta.verbose_name_plural if (model._meta.verbose_name_plural and counter > 1) else model._meta.verbose_name
        msg_success = _('Aktionen für {counter} {object_name} erfolgreich durchgeführt.').format(counter=counter, object_name=object_name)
        messages.success(request, msg_success)
                    
    else:
        messages.error(request, _('Keine Objekte ausgewählt.'))
        
    return redirect('list_object', model_name=model_name)


@login_required
@required_role('O')
def delete_object(request, model_name, id):
    # Check if model exists
    model, response = _check_model_exists(model_name)
    if response:
        return response

    # Get the object and check organization
    instance, response = _get_object_with_org_check(model, id, request)
    if response:
        return response

    # Delete the object
    instance.delete()
    
    # Use the helper function for redirection
    return _redirect_after_action(request, model_name)

@login_required
@required_role('O')
def get_cascade_info(request):
    """
    Get information about objects that would be deleted in a cascade operation.
    Uses Django's built-in admin function to ensure accurate cascade detection.
    
    Security:
    - Requires authentication and 'O' role
    - Validates model existence and organization access
    - Sanitizes output to prevent XSS
    
    Returns:
        JsonResponse with cascade_objects list containing:
        - model: User-friendly model name (plural)
        - count: Number of objects of this type
        - objects: List of individual objects
    """
    import logging
    logger = logging.getLogger(__name__)
    
    # Validate input parameters
    model_name = request.GET.get('model')
    object_id = request.GET.get('id')
    
    if not model_name or not object_id:
        logger.warning(f"Missing parameters: model={model_name}, id={object_id}")
        return JsonResponse({'error': 'Missing required parameters'}, status=400)
    
    # Validate object_id is numeric
    try:
        object_id = int(object_id)
    except (ValueError, TypeError):
        logger.warning(f"Invalid object_id: {object_id}")
        return JsonResponse({'error': 'Invalid object ID'}, status=400)
    
    logger.debug(f"get_cascade_info: model={model_name}, id={object_id}, user={request.user.username}")
    
    # Check if model exists and user has access
    model, response = _check_model_exists(model_name)
    if response:
        logger.warning(f"Model not found: {model_name}")
        return JsonResponse({'error': 'Model not found'}, status=404)
    
    # Special handling for 'user' model
    if model_name == 'user':
        try:
            model = User
            object_id = CustomUser.objects.get(id=object_id).user.id
        except CustomUser.DoesNotExist:
            logger.warning(f"CustomUser not found: {object_id}")
            return JsonResponse({'error': 'User not found'}, status=404)
    
    # Get the object and verify organization access
    instance, response = _get_object_with_org_check(model, object_id, request)
    if isinstance(response, HttpResponse):
        logger.warning(f"Access denied: {model.__name__} id={object_id}, user={request.user.username}")
        return JsonResponse({'error': 'Object not found or access denied'}, status=403)
    
    # Use Django's built-in admin function to get cascade information
    from django.contrib.admin.utils import get_deleted_objects, NestedObjects
    from django.contrib.admin import site as admin_site
    from django.db import DEFAULT_DB_ALIAS
    
    try:
        # Get detailed information about what will be deleted
        collector = NestedObjects(using=DEFAULT_DB_ALIAS)
        collector.collect([instance])
        
        # Also get the formatted output from Django admin for validation
        deletable_objects, model_count, perms_needed, protected = get_deleted_objects(
            [instance], 
            request, 
            admin_site
        )
        
        logger.info(f"Cascade info collected: {len(model_count)} model types, user={request.user.username}")
        
    except Exception as e:
        logger.error(f"Error getting cascade info: {e}", exc_info=True)
        return JsonResponse({'error': 'Error retrieving cascade information'}, status=500)
    
    # Build a detailed structure with individual objects
    related_objects = []
    total_objects = 0
    
    # Process collector.data to get individual objects grouped by model
    for model_class, instances in collector.data.items():
        # Skip the object being deleted itself
        filtered_instances = [obj for obj in instances if obj != instance]
        
        if not filtered_instances:
            continue
        
        # Get user-friendly model name (use plural for better UX)
        try:
            model_verbose = model_class._meta.verbose_name_plural
        except AttributeError:
            model_verbose = model_class.__name__
        
        # Build list of individual objects with their string representations
        objects_list = []
        for obj in filtered_instances:
            try:
                display_name = str(obj)
                # Sanitize and truncate long names
                display_name = display_name.strip()
                if len(display_name) > 100:
                    display_name = display_name[:97] + '...'
            except Exception as e:
                logger.debug(f"Error getting string representation: {e}")
                display_name = f"{model_class._meta.verbose_name} (ID: {obj.pk})"
            
            objects_list.append({
                'id': obj.pk,
                'display_name': display_name
            })
            total_objects += 1
        
        related_objects.append({
            'model': model_verbose,
            'count': len(filtered_instances),
            'objects': objects_list
        })
    
    logger.info(f"Returning cascade info: {len(related_objects)} model types, {total_objects} total objects")
    
    return JsonResponse({
        'cascade_objects': related_objects
    })

def ampel_mark_as_read(request):
    try:
        ampel_id = request.GET.get('id')
        if not ampel_id:
            return JsonResponse({'success': False, 'error': 'Ampel-ID is required'})
        ampel = Ampel2.objects.get(id=ampel_id)
        if not ampel:
            return JsonResponse({'success': False, 'error': 'Ampel not found'})
        ampel.read = True
        ampel.save()
        return JsonResponse({'success': True, 'message': 'Ampel markiert als gelesen'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})



@login_required
@required_role('O')
def list_aufgaben_table(request, scroll_to=None):
    """Render the aufgaben table page with minimal context - data loaded via AJAX."""
    
    person_cluster_param = request.GET.get('person_cluster_filter')
    
    if not person_cluster_param:
        person_cluster_param = request.COOKIES.get('selectedPersonCluster-aufgaben')
    if person_cluster_param is not None and person_cluster_param != 'None':
        try:
            person_cluster = PersonCluster.objects.get(id=int(person_cluster_param), org=request.user.org)
        except PersonCluster.DoesNotExist:
            person_cluster = None
    else:
        person_cluster = None
    
    # Get filter type from request or cookie for initial state
    filter_type = request.GET.get('f')
    if not filter_type:
        filter_type = request.COOKIES.get('filter_aufgaben_table') or 'None'

    # Get basic cluster data for filter display (lightweight)
    aufgaben_cluster = AufgabenCluster.objects.filter(org=request.user.org)
    if person_cluster:
        aufgaben_cluster = aufgaben_cluster.filter(person_cluster=person_cluster)
    
    # Convert filter_type to proper object for template consistency
    filter_object = None
    if filter_type and filter_type.isdigit() and filter_type != 'None':
        filter_object = aufgaben_cluster.filter(id=filter_type).first()

    if not person_cluster or person_cluster.aufgaben:
        context = {
            'current_person_cluster': person_cluster,
            'all_person_clusters': PersonCluster.objects.filter(org=request.user.org, aufgaben=True).order_by('view'),
            'aufgaben_cluster': aufgaben_cluster,
            'filter': filter_object,  # Use the object, not the string
            'scroll_to': scroll_to,
            'large_container': True,
            'ajax_loading': True  # Flag to indicate AJAX loading
        }
    else:
        context = {
            'error': f'{person_cluster.name} hat keine Aufgaben-Funktion aktiviert',
            'today': date.today()
        }

    # Create response with rendered template
    response = render(request, 'list_aufgaben_table.html', context=context)
    
    # Set cookie if filter_type is provided in request
    if request.GET.get('f'):
        if request.GET.get('f') == 'None':
            response.delete_cookie('filter_aufgaben_table')
        else:
            response.set_cookie('filter_aufgaben_table', request.GET.get('f'))
            
    if person_cluster:
        response.set_cookie('selectedPersonCluster-aufgaben', person_cluster.id)
    else:
        response.delete_cookie('selectedPersonCluster-aufgaben')

    return response

@login_required
@required_role('O')
def mark_task_as_done(request):
    try:
        user_aufgabe = UserAufgaben.objects.get(pk=request.GET.get('id'), org=request.user.org)
        user_aufgabe.erledigt = True
        user_aufgabe.erledigt_am = datetime.now().date()
        user_aufgabe.save()
        return JsonResponse({'success': True})
    except UserAufgaben.DoesNotExist:
        return JsonResponse({'success': False, 'error': _('Aufgabe nicht gefunden')}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
@required_role('O')
def send_task_reminder(request):
    try:
        user_aufgabe = UserAufgaben.objects.get(pk=request.GET.get('id'), org=request.user.org)
        if not user_aufgabe.user.customuser.mail_notifications:
            return JsonResponse({'success': False, 'error': _('E-Mail-Benachrichtigungen deaktiviert')}, status=400)
        if user_aufgabe.last_reminder:
            if user_aufgabe.last_reminder == date.today():
                return JsonResponse({'success': False, 'error': _('Erinnerung wurde bereits heute gesendet')}, status=400)
        user_aufgabe.send_reminder_email()
        return JsonResponse({'success': True})
    except UserAufgaben.DoesNotExist:
        return JsonResponse({'success': False, 'error': _('Aufgabe nicht gefunden')}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
@required_role('O')
def get_aufgaben_zwischenschritte(request):
    taskId = request.GET.get('taskId')
    if not UserAufgaben.objects.filter(pk=taskId, org=request.user.org).exists():
        return JsonResponse({'error': 'Nicht erlaubt'}, status=403)
    
    aufgabe = UserAufgaben.objects.get(pk=taskId)
    zwischenschritte = UserAufgabenZwischenschritte.objects.filter(user_aufgabe=aufgabe)
    
    zwischenschritte_data = []
    for zs in zwischenschritte:
        zwischenschritte_data.append({
            'id': zs.id,
            'name': zs.aufgabe_zwischenschritt.name,
            'beschreibung': zs.aufgabe_zwischenschritt.beschreibung,
            'erledigt': zs.erledigt
        })
    
    return JsonResponse({
        'task_name': aufgabe.aufgabe.name,
        'user_name': f"{aufgabe.user.first_name} {aufgabe.user.last_name}",
        'zwischenschritte': zwischenschritte_data
    })



@login_required
@required_role('OT')
def download_aufgabe(request, id):
    try:
        aufgabe = UserAufgaben.objects.get(pk=id, org=request.user.org)
        if not aufgabe.file:
            return render(request, '403.html', {'error_message': 'Keine Datei gefunden.'}, status=403)
        if not aufgabe.file.path:
            return render(request, '403.html', {'error_message': 'Datei nicht gefunden.'}, status=403)
        if not os.path.exists(aufgabe.file.path):
            return render(request, '403.html', {'error_message': 'Datei nicht gefunden.'}, status=403)
        
        if request.user.role == 'T':
            team_members = Team.objects.filter(org=request.user.org, user=request.user)
            if not aufgabe.aufgabe.visible_by_team:
                return render(request, '403.html', {'error_message': 'Du bist nicht berechtigt, diese Datei herunterzuladen. Die Aufgabe ist nicht für Team-Mitglieder sichtbar.'}, status=403)
            
            try:
                land = aufgabe.user.freiwilliger.einsatzland2
            except Exception as e:
                return render(request, '403.html', {'error_message': 'Du bist nicht berechtigt, diese Datei herunterzuladen. Freiwilliger nicht gefunden.'}, status=403)
            
            if land.id not in team_members.values_list('land__id', flat=True):
                    return render(request, '403.html', {'error_message': 'Du bist nicht berechtigt, diese Datei herunterzuladen. Du bist nicht als Teammitglied für diesen Freiwilligen zuständig.'}, status=403)
        
        if not aufgabe.file_downloaded_of.filter(id=request.user.id).exists():
            aufgabe.file_downloaded_of.add(request.user)
            aufgabe.save()
            
        # if pdf, open in new tab, otherwise download
        if aufgabe.file.name.lower().endswith('.pdf'):
            response = HttpResponse(aufgabe.file.read(), content_type='application/pdf')
            response['Content-Disposition'] = f'inline; filename="{aufgabe.file.name.replace(" ", "_")}"'
            return response
        else:
            response = HttpResponse(aufgabe.file.read(), content_type='application/octet-stream')
            response['Content-Disposition'] = f'attachment; filename="{aufgabe.file.name.replace(" ", "_")}"'
            return response
        
    except UserAufgaben.DoesNotExist:
        return render(request, '403.html', {'error_message': 'Du bist nicht berechtigt, auf diese Aufgabe zuzugreifen.'}, status=403)

@login_required
@required_role('O')
def statistik(request):
    field_name = request.GET.get('field')
    person_cluster_param = request.GET.get('person_cluster_filter')
    
    if not person_cluster_param:
        person_cluster_param = request.COOKIES.get('selectedPersonCluster-statistik')
    if person_cluster_param is not None and person_cluster_param != 'None':
        try:
            person_cluster = PersonCluster.objects.get(id=int(person_cluster_param), org=request.user.org)
        except PersonCluster.DoesNotExist:
            person_cluster = None
    else:
        person_cluster = None
    
    if person_cluster:
        freiwillige = Freiwilliger.objects.filter(org=request.user.org, user__customuser__person_cluster=person_cluster)
    else:
        freiwillige = Freiwilliger.objects.filter(org=request.user.org)
        
    fields_types_for_stats = ['T', 'C', 'D', 'B']
    if not 'selectedPersonCluster' in request.COOKIES:
        fields_types_for_stats.append('E')

    filter_for_fields = ['einsatzland2', 'einsatzstelle2']
    if not 'selectedPersonCluster' in request.COOKIES:
        filter_for_fields.append('personen_cluster')
    
    # Get regular fields
    all_fields = Freiwilliger._meta.fields
    fields = [field for field in all_fields if field.name in filter_for_fields]
    
    attributes = Attribute.objects.filter(org=request.user.org, type__in=fields_types_for_stats)
    if person_cluster:
        attributes = attributes.filter(person_cluster=person_cluster)
    
    # Convert attributes to field-like objects
    attribute_fields = [type('AttributeField', (), {
        'name': attr.name,
        'verbose_name': attr.name
    }) for attr in attributes]
    
    # Combine regular fields and attribute fields
    fields.extend(attribute_fields)
    
    context = {
        'freiwillige': freiwillige,
        'fields': fields,
        'attributes': attributes,
        'person_clusters': PersonCluster.objects.filter(org=request.user.org, view='F'),
        'current_person_cluster': person_cluster
    }
    
    return render(request, 'statistik.html', context)

@login_required
@required_role('O')
@require_http_methods(["GET"])
def ajax_statistik(request):
    field_name = request.GET.get('field')
    person_cluster_param = request.GET.get('person_cluster_filter')
    
    if not field_name:
        return JsonResponse({'error': 'Field parameter is required'}, status=400)
    
    if person_cluster_param and person_cluster_param != 'None':
        try:
            person_cluster = PersonCluster.objects.get(id=int(person_cluster_param), org=request.user.org)
            freiwillige = Freiwilliger.objects.filter(org=request.user.org, user__customuser__person_cluster=person_cluster)
        except PersonCluster.DoesNotExist:
            return JsonResponse({'error': 'Person cluster not found'}, status=404)
    else:
        freiwillige = Freiwilliger.objects.filter(org=request.user.org)
        
        
    # Check if it's a UserAttribute field
    if Attribute.objects.filter(name=field_name, org=request.user.org).exists():
        attribute = Attribute.objects.get(name=field_name, org=request.user.org)
        
        fields_types_for_stats = ['T', 'C', 'D', 'B']
        
        if attribute.type not in fields_types_for_stats:
            return JsonResponse({'error': 'Invalid field'}, status=400)
        
        stats = UserAttribute.objects.filter(
            org=request.user.org,
            attribute=attribute,
            user__in=freiwillige.values('user')
        ).values('value').annotate(count=Count('id')).order_by('value')
        
        data = {}
        for item in stats:
            value = item['value']
            if isinstance(value, int) and any(f.name == field_name and isinstance(f, ForeignKey) for f in Freiwilliger._meta.fields):
                related_obj = Freiwilliger._meta.get_field(field_name).related_model.objects.get(id=value)
                key = str(related_obj)
            else:
                key = str(value) if value is not None else '-'
                if key == '':
                    key = 'andere Benutzergruppe'
            data[key] = item['count']
        
        return JsonResponse(data)
    
    # Original code for Freiwilliger fields
    if field_name not in [f.name for f in Freiwilliger._meta.fields]:
        return JsonResponse({'error': 'Invalid field'}, status=400)
    
    stats = freiwillige.values(field_name)\
        .annotate(count=Count('id'))\
        .order_by(field_name)
    
    # Convert QuerySet to dictionary
    data = {}
    for item in stats:
        value = item[field_name]
        if isinstance(value, int) and any(f.name == field_name and isinstance(f, ForeignKey) for f in Freiwilliger._meta.fields):
            related_obj = Freiwilliger._meta.get_field(field_name).related_model.objects.get(id=value)
            key = str(related_obj)
        else:
            key = str(value) if value is not None else '-'
        data[key] = item['count']
    
    return JsonResponse(data)
        

@login_required
@required_role('O')
@require_http_methods(["POST"])
def send_registration_mail(request):
    try:
        data = json.loads(request.body)
        user_id = data.get('userId')
        
        # Get the CustomUser instance
        custom_user = CustomUser.objects.get(
            id=user_id,
            org=request.user.org
        )

        # Send the registration email
        custom_user.send_registration_email()
        
        return JsonResponse({
            'success': True,
            'message': 'Registrierungsmail erfolgreich gesendet',
            'einmalpasswort': custom_user.einmalpasswort
        })
        
    except CustomUser.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Benutzer nicht gefunden'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

def _check_model_exists(model_name, model=None):
    """
    Verify if a model exists for the given model_name.
    
    Args:
        model_name (str): The name of the model to check
        model (Model, optional): A model instance if already retrieved
        
    Returns:
        tuple: (model, response) where response is None if model exists or HttpResponse if not
    """
    if model is None and model_name in allowed_models_to_edit:
        return allowed_models_to_edit[model_name], None
    else:
        return None, HttpResponse(f'Kein Model für {model_name} gefunden')
    

def _get_object_with_org_check(model, object_id, request):
    """
    Get an object and verify it belongs to the user's organization.
    
    Args:
        model (Model): The model class
        object_id (int): The ID of the object to retrieve
        request: The HTTP request object
        
    Returns:
        tuple: (object, response) where response is None if check passes or HttpResponse if not
    """
    instance = get_object_or_404(model, id=object_id)
    
    if not instance.org == request.user.org:
        return None, HttpResponse('Nicht erlaubt')
    
    return instance, None

def _redirect_after_action(request, model_name, object_id=None):
    """
    Handle redirection after an object action (create/edit/delete).
    
    Args:
        request: The HTTP request object
        model_name (str): The name of the model
        object_id (int, optional): The ID of the object for highlighting
        
    Returns:
        HttpResponseRedirect: Redirect response
    """
    # Check for next parameter in GET
    next_url = request.GET.get('next')
    if next_url:
        return redirect(next_url)
    
    # Special case for useraufgaben
    if model_name.lower() == 'useraufgaben':
        return redirect('list_aufgaben_table')
    
    # TODO: Remove this because it is possible to edit aufgaben from the aufgaben list view instead of the table view
    if model_name.lower() == 'aufgabe':
        return redirect('list_aufgaben_table')
    
    # Standard case: redirect to list view with optional highlighting
    if object_id:
        return redirect('list_object_highlight', model_name=model_name, highlight_id=object_id)
    else:
        return redirect('list_object', model_name=model_name)
    
@login_required
@required_role('O')
def application_overview(request):
    # Get or create application texts
    application_texts, created = ApplicationText.objects.get_or_create(
        org=request.user.org,
        defaults={'welcome': '', 'footer': ''}
    )
    
    if request.method == 'POST':
        application_text_form = ORGforms.AddApplicationTextForm(request.POST, instance=application_texts)
        if application_text_form.is_valid():
            application_text_form.instance.org = request.user.org
            application_text_form.save()
            messages.success(request, 'Bewerbungstexte erfolgreich gespeichert')
        else:
            messages.error(request, 'Bewerbungstexte konnten nicht gespeichert werden')
        
        return redirect('application_overview')
    
    # Get all application questions
    text_questions = ApplicationQuestion.objects.filter(org=request.user.org).order_by('order')
    file_questions = ApplicationFileQuestion.objects.filter(org=request.user.org).order_by('order')
    
    # Get application statistics
    total_applications = Bewerber.objects.filter(org=request.user.org).count()
    completed_applications = Bewerber.objects.filter(org=request.user.org, abgeschlossen=True).count()
    
    # Calculate completion percentage
    completion_percentage = int(completed_applications / total_applications * 100) if total_applications > 0 else 0
    
    application_text_form = ORGforms.AddApplicationTextForm(instance=application_texts)
    
    context = {
        'application_texts': application_texts,
        'text_questions': text_questions,
        'file_questions': file_questions,
        'total_applications': total_applications,
        'completed_applications': completed_applications,
        'completion_percentage': completion_percentage,
        'application_text_form': application_text_form,
    }
    
    return render(request, 'application_overview.html', context)

@login_required
@required_role('O')
def application_list(request):
    filter_status = request.GET.get('status', 'completed')
    
    bewerber = Bewerber.objects.filter(org=request.user.org)
    
    if filter_status == 'completed':
        bewerber = bewerber.filter(abgeschlossen=True)
    elif filter_status == 'pending':
        bewerber = bewerber.filter(abgeschlossen=False)
        
    context = {
        'bewerber': bewerber,
        'current_filter': filter_status
    }
    
    return render(request, 'application_list.html', context)


@login_required
@required_role('O')
def application_detail(request, id):
    bewerber = Bewerber.objects.get(id=id)
    
    # Handle status change
    if request.method == 'POST' and 'status' in request.POST:
        new_status = request.POST.get('status')
        print(new_status)
        if new_status in dict(Bewerber.STATUS_CHOICES):
            if new_status == bewerber.status:
                bewerber.status = None
            else:
                bewerber.status = new_status
            bewerber.status_changed_at = timezone.now()
            bewerber.save()
            return redirect('application_detail', id=id)
        
    print(request.POST)
    if request.method == 'POST' and 'status_comment' in request.POST:
        status_comment = request.POST.get('status_comment')
        bewerber.status_comment = status_comment
        bewerber.save()
        return redirect('application_detail', id=id)
    
    if request.method == 'POST' and 'update_team_member' in request.POST:
        accessible_by_team_member_form = ORGforms.AccessibleByTeamMemberForm(request.POST, instance=bewerber, org=request.user.org)
        if accessible_by_team_member_form.is_valid():
            accessible_by_team_member_form.save()
            return redirect('application_detail', id=id)
    
    try:
        bewerber = Bewerber.objects.get(id=id, org=request.user.org)
        application_answers = ApplicationAnswer.objects.filter(user=bewerber.user).order_by('question__order')
        application_file_answers = ApplicationAnswerFile.objects.filter(user=bewerber.user).order_by('file_question__order')
        accessible_by_team_member_form = ORGforms.AccessibleByTeamMemberForm(instance=bewerber, org=request.user.org)
        
        context = {
            'bewerber': bewerber,
            'application_answers': application_answers,
            'application_file_answers': application_file_answers,
            'status_choices': Bewerber.STATUS_CHOICES,
            'accessible_by_team_member_form': accessible_by_team_member_form
        }
        return render(request, 'application_detail.html', context)
    except Bewerber.DoesNotExist:
        return redirect('application_list')


@login_required
@required_role('OET')
def application_answer_download(request, bewerber_id):
    bewerber = get_object_or_404(Bewerber, id=bewerber_id, org=request.user.org)
    
    if request.user.role in 'TE':
        if not bewerber.interview_persons.filter(id=request.user.id).exists():
            return render(request, '403.html', {'error_message': 'Du bist nicht berechtigt, diese Datei herunterzuladen. Du bist nicht als Interviewperson für diesen Bewerber:in zuständig.'}, status=403)
    
    # Create filename
    filename = f"bewerbung_{bewerber.user.first_name}_{bewerber.user.last_name}_{datetime.now().strftime('%Y%m%d')}.pdf"
    filename = "".join(c for c in filename if c.isalnum() or c in (' ', '-', '_', '.')).rstrip()
    filename = filename.replace(' ', '_')
    
    if bewerber.application_pdf:
        pdf_content = bewerber.application_pdf.read()
    else:
        pdf_content = generate_full_application_pdf(bewerber)
    
    return create_pdf_response(pdf_content, filename)

@login_required
@required_role('O')
def application_answer_download_fields(request, bewerber_id):
    bewerber = get_object_or_404(Bewerber, id=bewerber_id, org=request.user.org)
    
    # Get selected question IDs from request
    selected_question_ids = request.GET.getlist('questions')
    if not selected_question_ids:
        messages.error(request, 'Bitte wähle mindestens eine Frage aus.')
        return redirect('application_detail', id=bewerber_id)
    
    # Generate PDF using the new utils
    pdf_content = generate_selected_application_pdf(bewerber, selected_question_ids)
    
    # Create filename
    filename = f"bewerbung_auswahl_{bewerber.user.last_name}_{datetime.now().strftime('%Y%m%d')}.pdf"
    filename = "".join(c for c in filename if c.isalnum() or c in (' ', '-', '_', '.')).rstrip()
    filename = filename.replace(' ', '_')
    
    return create_pdf_response(pdf_content, filename)


def application_download_all_excel(request):
    
    seminar_filter = request.COOKIES.get('selectedSeminarFilter')
    if seminar_filter == 'yes':
        bewerber = Bewerber.objects.filter(org=request.user.org, seminar_bewerber__isnull=False)
    elif seminar_filter == 'no':
        bewerber = Bewerber.objects.filter(org=request.user.org, seminar_bewerber__isnull=True)
    else:
        bewerber = Bewerber.objects.filter(org=request.user.org)
    
    user_ids = bewerber.values_list('user_id', flat=True)
    
    # Create base DataFrame with bewerber data (including user_id for merging)
    df = pd.DataFrame(bewerber.values(
        'id', 'user_id', 'user__first_name', 'user__last_name', 'user__email', 'zuteilung__name', 'zuteilung__land__name', 'endbewertung', 'note'
    ))
    
    # Get user attributes with their types and pivot them to create columns for each attribute
    user_attributes = UserAttribute.objects.filter(user_id__in=user_ids).values(
        'user_id', 'attribute__name', 'attribute__type', 'value'
    )
    
    if user_attributes.exists():
        # Create a DataFrame from user attributes
        attr_df = pd.DataFrame(user_attributes)
        
        # Store attribute types for later formatting
        attribute_types = attr_df[['attribute__name', 'attribute__type']].drop_duplicates().set_index('attribute__name')['attribute__type'].to_dict()
        
        # Pivot the attributes so each attribute name becomes a column
        attr_pivot = attr_df.pivot_table(
            index='user_id',
            columns='attribute__name',
            values='value',
            aggfunc='first'  # In case there are duplicates, take the first value
        ).reset_index()
        
        # Merge with the main DataFrame on user_id
        df = df.merge(attr_pivot, on='user_id', how='left')
        
        # Format attribute columns based on their type
        for attr_name, attr_type in attribute_types.items():
            if attr_name in df.columns:
                if attr_type == 'N':  # Number (Zahl)
                    df[attr_name] = pd.to_numeric(df[attr_name], errors='coerce')
                elif attr_type == 'D':  # Date (Datum)
                    # Convert to datetime first, then format as German date string (dd.mm.yyyy)
                    df[attr_name] = pd.to_datetime(df[attr_name], errors='coerce')
                    df[attr_name] = df[attr_name].apply(lambda x: x.strftime('%d.%m.%Y') if pd.notna(x) else None)
                elif attr_type == 'B':  # Boolean (Wahrheitswert)
                    # Convert string values to boolean
                    df[attr_name] = df[attr_name].map(lambda x: True if str(x).lower() in ['true', '1', 'ja', 'yes'] else (False if str(x).lower() in ['false', '0', 'nein', 'no'] else None) if pd.notna(x) else None)
                # For 'T' (Text), 'L' (Long Text), 'E' (Email), 'P' (Phone), 'C' (Choice) - keep as string (no conversion needed)
    
    # Remove user_id from the final output (it was only needed for merging)
    if 'user_id' in df.columns:
        df = df.drop(columns=['user_id'])
    if 'id' in df.columns:
        df = df.drop(columns=['id'])
    
    # Rename columns to German headers
    column_rename_mapping = {
        'id': 'ID',
        'user__first_name': 'Vorname',
        'user__last_name': 'Nachname',
        'user__email': 'E-Mail',
        'status': 'Status',
        'status_comment': 'Status Kommentar',
        'abgeschlossen': 'Abgeschlossen',
        'gegenstand': 'Gegenstand',
        'endbewertung': 'Endbewertung',
        'note': 'Note',
        'zuteilung__name': 'Zuteilung Stelle',
        'zuteilung__land__name': 'Zuteilung Land'
    }
    df = df.rename(columns=column_rename_mapping)
    
    # create excel file and return response
    import io
    excel_buffer = io.BytesIO()
    df.to_excel(excel_buffer, index=False)
    excel_buffer.seek(0)
    response = HttpResponse(excel_buffer.getvalue(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="bewerbung_all_excel.xlsx"'
    return response
    


@login_required
@required_role('O')
@require_http_methods(["POST"])
def create_sticky_note(request):
    """Create a new sticky note."""
    notiz = request.POST.get('notiz')
    priority = request.POST.get('priority', 0)
    if not notiz:
        messages.error(request, 'Bitte gib eine Notiz ein.')
        return redirect('org_home')
    
    StickyNote.objects.create(
        org=request.user.org,
        user=request.user,
        notiz=notiz,
        pinned=True,
        date=timezone.now(),
        priority=priority
    )
    
    return redirect('org_home')

@login_required
@required_role('O')
@require_http_methods(["POST"])
def delete_sticky_note(request):
    """Delete a sticky note."""
    notiz_id = request.POST.get('notiz_id')
    if not notiz_id:
        messages.error(request, 'Keine Notiz-ID angegeben.')
        return redirect('org_home')
    
    try:
        notiz = StickyNote.objects.get(
            id=notiz_id,
            org=request.user.org,
            user=request.user
        )
        notiz.delete()
    except StickyNote.DoesNotExist:
        messages.error(request, 'Notiz konnte nicht gefunden werden')
    
    return redirect('org_home')


# Helper functions for AJAX operations
def _parse_ajax_request(request):
    """Parse and validate AJAX request body."""
    try:
        return json.loads(request.body), None
    except json.JSONDecodeError:
        return None, JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)

def _get_user_aufgabe_with_org_check(aufgabe_id, org):
    """Get UserAufgabe with organization check."""
    try:
        return UserAufgaben.objects.get(pk=aufgabe_id, org=org), None
    except UserAufgaben.DoesNotExist:
        return None, JsonResponse({'success': False, 'error': 'Aufgabe nicht gefunden'}, status=404)

def _get_aufgabe_with_org_check(aufgabe_id, org):
    """Get Aufgabe2 with organization check."""
    try:
        return Aufgabe2.objects.get(id=aufgabe_id, org=org), None
    except Aufgabe2.DoesNotExist:
        return None, JsonResponse({'success': False, 'error': 'Aufgabe nicht gefunden'}, status=404)

def _get_user_with_org_check(user_id, org):
    """Get User with organization check."""
    try:
        user = User.objects.get(id=user_id)
        if user.customuser.org != org:
            return None, JsonResponse({'success': False, 'error': 'Benutzer nicht gefunden'}, status=404)
        return user, None
    except User.DoesNotExist:
        return None, JsonResponse({'success': False, 'error': 'Benutzer nicht gefunden'}, status=404)

def _check_user_task_permission(user, aufgabe):
    """Check if user has permission for the task based on person cluster."""
    if aufgabe.person_cluster.exists() and user.customuser.person_cluster:
        if not user.customuser.person_cluster in aufgabe.person_cluster.all():
            return JsonResponse({
                'success': False, 
                'error': f'{user.get_full_name()} ({user.customuser.person_cluster.name}) has no access to task {aufgabe.name}'
            }, status=400)
    return None

def _handle_ajax_error(e):
    """Handle common AJAX errors."""
    return JsonResponse({'success': False, 'error': str(e)}, status=500)

# AJAX endpoints for task operations
@login_required
@required_role('O')
@require_http_methods(["POST"])
def ajax_update_task_status(request):
    """Update task status via AJAX."""
    data, error_response = _parse_ajax_request(request)
    if error_response:
        return error_response
    
    try:
        aufgabe_id = data.get('aufgabe_id')
        pending = data.get('pending')
        erledigt = data.get('erledigt')
        
        user_aufgabe, error_response = _get_user_aufgabe_with_org_check(aufgabe_id, request.user.org)
        if error_response:
            return error_response
        
        user_aufgabe.pending = pending
        user_aufgabe.erledigt = erledigt
        user_aufgabe.erledigt_am = timezone.now().date() if (erledigt or pending) else None
        user_aufgabe.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Task status updated successfully',
            'new_status': {
                'pending': user_aufgabe.pending,
                'erledigt': user_aufgabe.erledigt,
                'erledigt_am': user_aufgabe.erledigt_am.strftime('%d.%m.%Y') if user_aufgabe.erledigt_am else None
            }
        })
        
    except Exception as e:
        return _handle_ajax_error(e)


@login_required
@required_role('O')
@require_http_methods(["POST"])
def ajax_delete_task_file(request):
    """Delete task file via AJAX."""
    data, error_response = _parse_ajax_request(request)
    if error_response:
        return error_response
    
    try:
        aufgabe_id = data.get('aufgabe_id')
        
        user_aufgabe, error_response = _get_user_aufgabe_with_org_check(aufgabe_id, request.user.org)
        if error_response:
            return error_response
        
        if user_aufgabe.file:
            user_aufgabe.file.delete()
            user_aufgabe.save()
            return JsonResponse({'success': True, 'message': 'File deleted successfully'})
        else:
            return JsonResponse({'success': False, 'error': 'No file to delete'}, status=400)
        
    except Exception as e:
        return _handle_ajax_error(e)


@login_required
@required_role('O')
@require_http_methods(["POST"])
def ajax_assign_tasks_by_country(request):
    """Assign tasks by country via AJAX."""
    data, error_response = _parse_ajax_request(request)
    if error_response:
        return error_response
    
    try:
        aufgabe_id = data.get('aufgabe_id')
        country_id = data.get('country_id')
        
        aufgabe, error_response = _get_aufgabe_with_org_check(aufgabe_id, request.user.org)
        if error_response:
            return error_response
        
        users, _ = get_filtered_user_queryset(request, 'aufgaben')
        custom_users = CustomUser.objects.filter(
            org=request.user.org, 
            user__in=users, 
            person_cluster__in=aufgabe.person_cluster.all()
        )
        
        assigned_count = 0
        for custom_user in custom_users:
            if (Freiwilliger.objects.filter(org=request.user.org, user=custom_user.user, einsatzland2=country_id).exists() or 
                Team.objects.filter(org=request.user.org, user=custom_user.user, land=country_id).exists()):
                user_aufgabe, created = UserAufgaben.objects.get_or_create(
                    org=request.user.org,
                    user=custom_user.user,
                    aufgabe=aufgabe
                )
                if created:
                    assigned_count += 1
        
        return JsonResponse({
            'success': True,
            'message': f'Tasks assigned to {assigned_count} users',
            'assigned_count': assigned_count
        })
        
    except Exception as e:
        return _handle_ajax_error(e)


@login_required
@required_role('O')
@require_http_methods(["POST"])
def ajax_assign_task(request):
    """Assign a task to a specific user via AJAX."""
    data, error_response = _parse_ajax_request(request)
    if error_response:
        return error_response
    
    try:
        user_id = data.get('user_id')
        aufgabe_id = data.get('aufgabe_id')
        
        # Get user and check organization
        user, error_response = _get_user_with_org_check(user_id, request.user.org)
        if error_response:
            return error_response
        
        # Get aufgabe and check organization
        aufgabe, error_response = _get_aufgabe_with_org_check(aufgabe_id, request.user.org)
        if error_response:
            return error_response
        
        # Check user permissions for this task
        permission_error = _check_user_task_permission(user, aufgabe)
        if permission_error:
            return permission_error
        
        # Create or get the user task
        user_aufgabe, created = UserAufgaben.objects.get_or_create(
            org=request.user.org,
            user=user,
            aufgabe=aufgabe
        )
        
        message = 'Task assigned successfully' if created else 'Task was already assigned'
        
        return JsonResponse({
            'success': True,
            'message': message,
            'created': created,
            'task_id': user_aufgabe.id
        })
        
    except Exception as e:
        return _handle_ajax_error(e)


@login_required
@required_role('O')
@require_http_methods(["POST"])
def ajax_assign_task_to_all(request):
    """Assign a task to all eligible users via AJAX."""
    data, error_response = _parse_ajax_request(request)
    if error_response:
        return error_response
    
    try:
        aufgabe_id = data.get('aufgabe_id')
        person_cluster_id = data.get('person_cluster_id')
        
        # Get aufgabe and check organization
        aufgabe, error_response = _get_aufgabe_with_org_check(aufgabe_id, request.user.org)
        if error_response:
            return error_response
        
        users = User.objects.filter(customuser__person_cluster__isnull=False, customuser__org=request.user.org, customuser__person_cluster__in=aufgabe.person_cluster.all())
        if person_cluster_id and person_cluster_id not in ['None', 'undefined', '']:
            try:
                person_cluster_id_int = int(person_cluster_id)
                person_cluster = PersonCluster.objects.filter(id=person_cluster_id_int, org=request.user.org)
                if person_cluster.exists():
                    users = users.filter(customuser__person_cluster=person_cluster.first())
            except (ValueError, TypeError):
                # Invalid person_cluster_id, skip filtering by person cluster
                pass
            
        assigned_count = 0
        error_messages = []
        
        for user in users:
            try:
                # Check organization match
                if user.customuser.org != request.user.org:
                    continue
                
                # Check person cluster compatibility
                permission_error = _check_user_task_permission(user, aufgabe)
                if permission_error:
                    name = f'{user.first_name + " " if user.first_name else ""}{user.last_name + " " if user.last_name else ""}{user.username if not user.first_name and not user.last_name else ""}'
                    error_messages.append(f'{name} ({user.customuser.person_cluster.name}) has no access to task {aufgabe.name}')
                    continue
                
                # Create or get the user task
                user_aufgabe, created = UserAufgaben.objects.get_or_create(
                    org=request.user.org,
                    user=user,
                    aufgabe=aufgabe
                )
                
                if created:
                    assigned_count += 1
                    
            except Exception as e:
                error_messages.append(f'Error assigning to {user.get_full_name()}: {str(e)}')
        
        return JsonResponse({
            'success': True,
            'message': f'Task assigned to {assigned_count} users',
            'assigned_count': assigned_count,
            'errors': error_messages if error_messages else None
        })
        
    except Exception as e:
        return _handle_ajax_error(e)


@login_required
@required_role('O')
def copy_links(request):
    page_elements = [
        {
        'name': 'Allgemein',
        'pages': [
            {
                'name': 'Posts',
                'url': reverse('posts_overview')
            },
            {
                'name': 'Dokumente',
                'url': reverse('dokumente')
            },
            {
                'name': 'Bilder',
                'url': reverse('bilder')
            },
            {
                'name': 'Bilder hochladen',
                'url': reverse('bild')
            },
            {
                'name': 'Profil',
                'url': reverse('profil')
            },
            {
                'name': 'Einstellungen',
                'url': reverse('settings')
            }
        ]
    },
        {
        'name': 'Freiwillige',
        'pages': [
            {
                'name': 'Aufgaben',
                'url': reverse('aufgaben')
            },
            {
                'name': 'Kalender',
                'url': reverse('kalender')
            },
            {
                'name': 'Ampelmeldungen abgeben',
                'url': reverse('ampel')
            },
            {
                'name': 'Notfallkontakte eintragen',
                'url': reverse('notfallkontakte')
            },
            {
                'name': 'Einsatzlandinformationen einsehen',
                'url': reverse('laenderinfo')
            }
        ]
    }, 
        {
        'name': 'Team',
        'pages': [
            {
                'name': 'Kontakte',
                'url': reverse('team_contacts')
            },
            {
                'name': 'Ampelmeldung einsehen',
                'url': reverse('list_ampel')
            },
            {
                'name': 'Einsatzstelleninformationen',
                'url': reverse('einsatzstellen_info')
            },
            {
                'name': 'Einsatzstellen Notizen',
                'url': reverse('einsatzstellen_notiz')
            },
            {
                'name': 'Länderinformationen',
                'url': reverse('laender_info')
            }
        ]
    },
        {
        'name': 'Ehemalige',
        'pages': [
            {
                'name': 'Länderinformationen',
                'url': reverse('laender_info')
            },
            {
                'name': 'Einsatzstelleninformationen',
                'url': reverse('einsatzstellen_info')
            }
        ]
    },
        {
        'name': 'Bewerber',
        'pages': [
            {
                'name': 'Zuteilung ansehen',
                'url': reverse('my_assignment')
            }
        ]
    }
    ]
    
    return render(request, 'copy_links.html', {'page_elements': page_elements})


@login_required
@required_role('O')
def change_requests(request):
    """List all pending change requests for review."""
    pending_requests = ChangeRequest.objects.filter(
        org=request.user.org,
        status='pending'
    ).select_related('requested_by').order_by('-created_at')
    
    # Get all change requests for statistics
    all_requests = ChangeRequest.objects.filter(org=request.user.org)
    
    context = {
        'change_requests': pending_requests,
        'total_pending': pending_requests.count(),
        'total_approved': all_requests.filter(status='approved').count(),
        'total_rejected': all_requests.filter(status='rejected').count(),
    }
    
    return render(request, 'change_requests.html', context)


@login_required
@required_role('O')
def review_change_request(request, request_id):
    """Review and approve/reject a change request."""
    change_request = get_object_or_404(ChangeRequest, id=request_id, org=request.user.org)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        review_comment = request.POST.get('review_comment', '')
        
        if action in ['approved', 'rejected']:
            change_request.status = action
            change_request.reviewed_by = request.user
            change_request.reviewed_at = timezone.now()
            change_request.review_comment = review_comment
            change_request.save()
            
            if action == 'approved':
                try:
                    # Apply the changes
                    change_request.apply_changes()
                    messages.success(request, 'Änderungsantrag wurde genehmigt und angewendet.')
                except Exception as e:
                    messages.error(request, f'Fehler beim Anwenden der Änderungen: {str(e)}')
                    change_request.status = 'pending'  # Revert status on error
                    change_request.save()
            else:
                messages.success(request, 'Änderungsantrag wurde abgelehnt.')
            
            # Notify the requester
            from Global.views_change_requests import _notify_requester_of_decision
            _notify_requester_of_decision(change_request)
            
        return redirect('change_requests')
    
    # Get the object and current values for comparison
    obj = change_request.get_object()
    field_changes_display = change_request.get_field_changes_display()
    
    context = {
        'change_request': change_request,
        'object': obj,
        'field_changes_display': field_changes_display,
    }
    
    return render(request, 'review_change_request.html', context)


@login_required
@required_role('O')
def change_request_history(request):
    """View all change requests (approved, rejected, pending)."""
    all_requests = ChangeRequest.objects.filter(
        org=request.user.org
    ).select_related('requested_by', 'reviewed_by').order_by('-created_at')
    
    # Filter by status if requested
    status_filter = request.GET.get('status')
    if status_filter and status_filter in ['pending', 'approved', 'rejected', 'cancelled']:
        all_requests = all_requests.filter(status=status_filter)
    
    # Pagination
    paginator = Paginator(all_requests, 25)  # Show 25 requests per page
    page = request.GET.get('page')
    
    try:
        change_requests = paginator.page(page)
    except PageNotAnInteger:
        change_requests = paginator.page(1)
    except EmptyPage:
        change_requests = paginator.page(paginator.num_pages)
    
    context = {
        'change_requests': change_requests,
        'status_filter': status_filter,
        'status_choices': ChangeRequest.STATUS_CHOICES,
    }
    
    return render(request, 'change_request_history.html', context)


@login_required
@required_role('O')
@require_http_methods(["GET"])
def ajax_load_aufgaben_table_data(request):
    """Load aufgaben table data via AJAX - returns JSON for client-side rendering."""
    try:
        person_cluster_param = request.GET.get('person_cluster_filter')
        
        if person_cluster_param is not None and person_cluster_param != 'None':
            person_cluster = PersonCluster.objects.get(id=int(person_cluster_param), org=request.user.org)
            users = User.objects.filter(customuser__person_cluster=person_cluster, customuser__org=request.user.org).order_by('first_name', 'last_name')
            aufgaben = Aufgabe2.objects.filter(org=request.user.org, person_cluster=person_cluster)
        else:
            person_cluster = None
            users = User.objects.filter(customuser__org=request.user.org, customuser__person_cluster__isnull=False, customuser__person_cluster__aufgaben=True).order_by('-customuser__person_cluster', 'first_name', 'last_name')
            aufgaben = Aufgabe2.objects.filter(org=request.user.org)
        
        # Apply ordering
        aufgaben = aufgaben.order_by(
            'faellig_art',
            'faellig_monat',
            'faellig_tag',
            'faellig_tage_nach_start',
            'faellig_tage_vor_ende',
            'name'
        )

        # Get filter type from request or cookie
        filter_type = request.GET.get('f')
        if not filter_type:
            filter_type = request.COOKIES.get('filter_aufgaben_table') or 'None'

        # Apply filter if provided
        if filter_type and filter_type.isdigit() and filter_type != 'None':
            aufgaben_cluster = AufgabenCluster.objects.filter(id=filter_type)
            if aufgaben_cluster:
                aufgaben = aufgaben.filter(faellig_art__in=aufgaben_cluster)
                filter_type = aufgaben_cluster.first()

        # Optimized query for user_aufgaben with better prefetching
        user_aufgaben = UserAufgaben.objects.filter(
            org=request.user.org,
            user__in=users,
            aufgabe__in=aufgaben
        ).select_related('user', 'aufgabe', 'user__customuser').prefetch_related(
            Prefetch(
                'useraufgabenzwischenschritte_set',
                queryset=UserAufgabenZwischenschritte.objects.all(),
                to_attr='prefetched_zwischenschritte'
            ),
            'file_downloaded_of'
        )

        # Prefetch person_cluster relationships for aufgaben to avoid N+1 queries
        aufgaben = aufgaben.prefetch_related('person_cluster')
        
        # Prefetch customuser and person_cluster for users to avoid N+1 queries
        users = users.select_related('customuser', 'customuser__person_cluster')

        # Create a lookup dictionary for faster access
        user_aufgaben_dict = {}
        for ua in user_aufgaben:
            if ua.user_id not in user_aufgaben_dict:
                user_aufgaben_dict[ua.user_id] = {}
            user_aufgaben_dict[ua.user_id][ua.aufgabe_id] = ua

        # Build eligibility map: which aufgaben is each user eligible for?
        # eligible_map[user_id] = set(aufgabe_ids)
        eligible_map = {}
        for user in users:
            if hasattr(user, 'customuser') and user.customuser.person_cluster:
                user_person_cluster = user.customuser.person_cluster
                eligible_aufgaben = set()
                for aufgabe in aufgaben:
                    # Check if user's person_cluster is in aufgabe's person_cluster
                    if user_person_cluster in aufgabe.person_cluster.all():
                        eligible_aufgaben.add(aufgabe.id)
                eligible_map[user.id] = eligible_aufgaben
            else:
                eligible_map[user.id] = set()

        # Build sparse dictionaries instead of dense matrix
        # user_aufgaben_assigned[user_id][aufgabe_id] = {...} for assigned tasks
        # user_aufgaben_eligible[user_id] = [aufgabe_id, ...] for eligible but unassigned
        user_aufgaben_assigned = {}
        user_aufgaben_eligible = {}
        
        for user in users:
            user_id = user.id
            user_aufgaben_assigned[user_id] = {}
            user_aufgaben_eligible[user_id] = []
            
            eligible_aufgaben = eligible_map.get(user_id, set())
            
            for aufgabe in aufgaben:
                aufgabe_id = aufgabe.id
                ua = user_aufgaben_dict.get(user_id, {}).get(aufgabe_id, None)
                
                if ua:
                    # User has this aufgabe assigned
                    zwischenschritte = ua.prefetched_zwischenschritte
                    zwischenschritte_count = len(zwischenschritte)
                    zwischenschritte_done_count = sum(1 for z in zwischenschritte if z.erledigt)
                    
                    # Only get file downloaded by names if file exists (lazy load optimization)
                    file_downloaded_of_names = None
                    if ua.file:
                        file_downloaded_of_names = ', '.join([
                            f"{u.first_name} {u.last_name}" for u in ua.file_downloaded_of.all()
                        ])
                    
                    user_aufgaben_assigned[user_id][aufgabe_id] = {
                        'user_aufgabe': {
                            'id': ua.id,
                            'aufgabe_name': ua.aufgabe.name,
                            'erledigt': ua.erledigt,
                            'erledigt_am': ua.erledigt_am.isoformat() if ua.erledigt_am else None,
                            'pending': ua.pending,
                            'faellig': ua.faellig.isoformat() if ua.faellig else None,
                            'file': bool(ua.file),
                            'file_name': ua.file.name.split('/')[-1] if ua.file else None,
                            'file_downloaded_of_names': file_downloaded_of_names,
                            'mail_notifications': ua.user.customuser.mail_notifications if hasattr(ua.user, 'customuser') else True,
                            'currently_sending': getattr(ua, 'currently_sending', False),
                            'last_reminder': ua.last_reminder.isoformat() if hasattr(ua, 'last_reminder') and ua.last_reminder else None,
                        },
                        'zwischenschritte_done_open': f'{zwischenschritte_done_count}/{zwischenschritte_count}' if zwischenschritte_count > 0 else False,
                        'zwischenschritte_done': zwischenschritte_done_count == zwischenschritte_count and zwischenschritte_count > 0,
                    }
                elif aufgabe_id in eligible_aufgaben:
                    # User is eligible but aufgabe not assigned
                    user_aufgaben_eligible[user_id].append(aufgabe_id)
                # If neither assigned nor eligible, we don't include it (sparse format)

        # Get countries for users
        countries = Einsatzland2.objects.filter(org=request.user.org)

        # Serialize data for JSON response
        users_data = [{
            'id': user.id,
            'username': user.username,
            'first_name': user.first_name,
            'last_name': user.last_name,
        } for user in users]

        aufgaben_data = [{
            'id': aufgabe.id,
            'name': aufgabe.name,
            'beschreibung': aufgabe.beschreibung,
            'mitupload': aufgabe.mitupload,
            'wiederholung': aufgabe.wiederholung,
        } for aufgabe in aufgaben]

        response_data = {
            'success': True,
            'data': {
                'users': users_data,
                'aufgaben': aufgaben_data,
                'user_aufgaben_assigned': user_aufgaben_assigned,
                'user_aufgaben_eligible': user_aufgaben_eligible,
                'countries': list(countries.values('id', 'name')),
                'today': date.today().isoformat(),
                'current_person_cluster': person_cluster.id if person_cluster else None,
            }
        }
        return JsonResponse(response_data)
    
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"AJAX Error: {str(e)}")
        print(f"Traceback: {error_details}")
        return JsonResponse({
            'success': False,
            'error': f'Fehler beim Laden der Daten: {str(e)}'
        }, status=500)