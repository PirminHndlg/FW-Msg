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
from django.db.models import Max, F, Min
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from functools import wraps
from dateutil.relativedelta import relativedelta
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
    EinsatzstelleNotiz
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

class PersonenClusterFilteredQuerySet(QuerySet):
    """Custom QuerySet that automatically filters by personen_cluster from cookie."""
    def __init__(self, *args, **kwargs):
        self._person_cluster_id = None
        super().__init__(*args, **kwargs)

    def set_person_cluster_id(self, person_cluster_id):
        self._person_cluster_id = person_cluster_id
        return self

    def _clone(self):
        clone = super()._clone()
        clone._person_cluster_id = self._person_cluster_id
        return clone

    def filter(self, *args, **kwargs):
        queryset = super().filter(*args, **kwargs)
        if self._person_cluster_id and self.model == Freiwilliger:
            queryset = queryset.filter(person_cluster=self._person_cluster_id)
        return queryset

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
        return PersonCluster.objects.get(id=person_cluster_id) if person_cluster_id else None
    

def set_person_cluster(request, person_cluster):
    response = HttpResponseRedirect(request.META.get('HTTP_REFERER', '/'))
    if 'selectedPersonCluster' in request.COOKIES:
        response.delete_cookie('selectedPersonCluster')
    if 'selectedPersonClusterName' in request.COOKIES:
        response.delete_cookie('selectedPersonClusterName')
    response.set_cookie('selectedPersonCluster', person_cluster.id)
    response.set_cookie('selectedPersonClusterName', person_cluster.name)
    return response


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


def filter_person_cluster(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        person_cluster = get_person_cluster(request)

        original_get_queryset_freiwilliger = Freiwilliger.objects.get_queryset
        original_get_queryset_aufgabe = Aufgabe2.objects.get_queryset

        def get_person_cluster_queryset(manager):
            base_qs = original_get_queryset_freiwilliger()
            if person_cluster:
                return base_qs.filter(user__customuser__person_cluster=person_cluster)
            return base_qs
        
        def get_person_cluster_queryset_aufgabe(manager):
            base_qs = original_get_queryset_aufgabe()
            if person_cluster:
                return base_qs.filter(Q(person_cluster=person_cluster) | Q(person_cluster=None))
            return base_qs
    
        Freiwilliger.objects.get_queryset = get_person_cluster_queryset.__get__(Freiwilliger.objects)
        Aufgabe2.objects.get_queryset = get_person_cluster_queryset_aufgabe.__get__(Aufgabe2.objects)
        #CustomUser.objects.get_queryset = get_person_cluster_queryset_user.__get__(CustomUser.objects)

        try:
            return view_func(request, *args, **kwargs)
        finally:
            Freiwilliger.objects.get_queryset = original_get_queryset_freiwilliger
            Aufgabe2.objects.get_queryset = original_get_queryset_aufgabe
            
    return _wrapped_view

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
@filter_person_cluster
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
@filter_person_cluster
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
@filter_person_cluster
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
@filter_person_cluster
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
@filter_person_cluster
def add_aufgabe(request):
    if request.method == 'POST':
        form = ORGforms.AddAufgabeForm(request.POST, request.FILES, request=request)
        if form.is_valid():
            save_form(request, form)
            next_url = request.GET.get('next')
            if next_url:
                return redirect(next_url)
            return redirect('list_object', model_name='aufgabe')
        else:
            messages.error(request, 'Fehler beim Erstellen der Aufgabe. Bitte überprüfen Sie die Eingaben.')
            print("Form errors:", form.errors)
            print("Non-field errors:", form.non_field_errors())
            if hasattr(form, 'zwischenschritte'):
                print("Zwischenschritte errors:", form.zwischenschritte.errors)
            return render(request, 'add_aufgabe.html', {'form': form})
    form = ORGforms.AddAufgabeForm(request=request)
    return render(request, 'add_aufgabe.html', {'form': form})

@login_required
@required_role('O')
@filter_person_cluster
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
                return HttpResponse('Nicht erlaubt')
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
@filter_person_cluster
def delete_zwischenschritt(request):
    zwischenschritt_id = request.POST.get('zwischenschritt_id')
    zwischenschritt = AufgabeZwischenschritte2.objects.get(id=zwischenschritt_id)
    zwischenschritt.delete()
    return redirect('edit_object', model_name='aufgabe', id=zwischenschritt.aufgabe.id)


@login_required
@required_role('O')
@filter_person_cluster
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
@filter_person_cluster
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
@filter_person_cluster
def edit_object(request, model_name, id):
    # Check if model exists and has a form mapping
    model, response = _check_model_exists(model_name.lower())
    if response:
        return response
    
    if not model in ORGforms.model_to_form_mapping:
        return HttpResponse(f'Kein Formular für {model_name} gefunden')

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
@filter_person_cluster
def list_object(request, model_name, highlight_id=None):
    # Check if model exists using the helper function
    model, response = _check_model_exists(model_name)
    if response:
        return response

    # Check if this model should use the old approach (freiwilliger and team)
    if model_name.lower() in ['freiwilliger', 'team']:
        return _list_object_legacy(request, model_name, model, highlight_id)
    
    # Use djangotables2 for other models
    return _list_object_with_tables2(request, model_name, model, highlight_id)


def _list_object_legacy(request, model_name, model, highlight_id=None):
    """Legacy implementation for freiwilliger and team models"""
    # Get base queryset with organization filter
    objects = model.objects.filter(org=request.user.org)
    
    # Get person cluster and check permissions
    person_cluster = get_person_cluster(request)
    error = _check_person_cluster_permissions(model, person_cluster)
    
    # Get field metadata and model fields
    field_metadata, model_fields = _get_field_metadata(model)
    
    # Apply model-specific logic
    objects = _apply_model_specific_logic(model, objects, person_cluster, field_metadata, model_fields)
    
    # Add many-to-many fields
    field_metadata.extend(_get_m2m_fields(model))
    
    # Count total objects before pagination
    total_objects_count = objects.count()
    
    # Apply pagination
    paginated_objects, query_string = _apply_pagination(objects, request)
    
    return render(request, 'list_objects.html',
                 {'objects': paginated_objects, 
                  'field_metadata': field_metadata, 
                  'model_name': model_name,
                  'verbose_name': model._meta.verbose_name_plural,
                  'highlight_id': highlight_id,
                  'error': error,
                  'paginator': paginated_objects.paginator,
                  'page_obj': paginated_objects,
                  'total_count': total_objects_count,
                  'query_string': query_string,
                  'large_container': True})


def _list_object_with_tables2(request, model_name, model, highlight_id=None):
    """New implementation using djangotables2"""
    from django_tables2 import RequestConfig
    from .tables import MODEL_TABLE_MAPPING
    
    # Get person cluster and check permissions
    person_cluster = get_person_cluster(request)
    error = _check_person_cluster_permissions(model, person_cluster)
    
    # Get base queryset with organization filter
    objects = model.objects.filter(org=request.user.org)
    
    # Get field metadata and model fields for model-specific logic
    field_metadata, model_fields = _get_field_metadata(model)
    
    # Apply model-specific logic
    objects = _apply_model_specific_logic(model, objects, person_cluster, field_metadata, model_fields)
    
    # Count total objects before filtering
    total_objects_count = objects.count()
    
    # Apply search filter if provided
    search_query = request.GET.get('search', '').strip()
    if search_query:
        objects = _apply_search_filter(objects, model, search_query)
    
    # Get the appropriate table class
    table_class = MODEL_TABLE_MAPPING.get(model_name.lower())
    if not table_class:
        # Fallback to legacy implementation if no table defined
        return _list_object_legacy(request, model_name, model, highlight_id)
    
    # Create table instance
    table = table_class(objects, model_name=model_name.lower())

    # Configure pagination and sorting
    RequestConfig(request).configure(table)

    return render(request, 'list_objects_table.html', {
        'table': table,
        'model_name': model_name,
        'verbose_name': model._meta.verbose_name_plural,
        'highlight_id': highlight_id,
        'error': error,
        'total_count': total_objects_count,
        'search_query': search_query,
        'large_container': True
    })


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

def _apply_model_specific_logic(model, objects, person_cluster, field_metadata, model_fields):
    """Apply model-specific logic to the queryset."""
    model_name = model._meta.object_name
    
    # Common user fields
    user_fields = [
        {'name': 'user_first_name', 'verbose_name': 'Vorname', 'type': 'T'},
        {'name': 'user_last_name', 'verbose_name': 'Nachname', 'type': 'T'},
        {'name': 'user_email', 'verbose_name': 'Email', 'type': 'E'}
    ]
    
    if model_name in ['Freiwilliger', 'Team']:
        objects = _handle_freiwilliger_team_model(objects, person_cluster, field_metadata, model_fields, user_fields, model_name)
        if model_name == 'Freiwilliger':
            pass
    else:
        objects = _handle_default_model(objects, model_fields, person_cluster)
    
    return objects

def _handle_freiwilliger_team_model(objects, person_cluster, field_metadata, model_fields, user_fields, model_name):
    """Handle Freiwilliger and Team model specific logic."""
    objects = objects.order_by('user__first_name', 'user__last_name')
    
    # Add user fields
    field_metadata[0:0] = user_fields
    model_fields[0:0] = [field['name'] for field in user_fields]
    objects = objects.annotate(
        **{field['name']: F(f'user__{field["name"].replace("user_", "")}') 
           for field in user_fields}
    )
    
    if model_name.lower() == 'freiwilliger':
        # Add birthday field
        field_metadata.append({'name': 'geburtsdatum', 'verbose_name': 'Geburtsdatum', 'type': 'D'})
        model_fields.append('geburtsdatum')
        objects = objects.annotate(geburtsdatum=F('user__customuser__geburtsdatum'))
    
    # Handle attributes
    if person_cluster and objects.exists():
        attributes = Attribute.objects.filter(org=objects.first().org, person_cluster=person_cluster)
        for attr in attributes:
            field_metadata.append({
                'name': attr.name,
                'verbose_name': attr.name,
                'type': attr.type
            })
            objects = objects.annotate(**{
                attr.name.replace(" ", "_"): Subquery(
                    UserAttribute.objects.filter(
                        attribute__id=attr.id,
                        user_id=OuterRef('user_id'),
                        org=objects.first().org
                    ).values('value')[:1]
                )
            })
    
    return objects

def _handle_default_model(objects, model_fields, person_cluster=None):
    """Handle default model ordering logic."""
    if 'freiwilliger' in model_fields:
        objects = objects.order_by('freiwilliger__first_name', 'freiwilliger__last_name')
    elif 'first_name' in model_fields:
        objects = objects.order_by('first_name')
    elif 'last_name' in model_fields:
        objects = objects.order_by('last_name')
    elif 'name' in model_fields:
        objects = objects.order_by('name')
    if person_cluster:
        print(model_fields, person_cluster)
        if 'person_cluster' in model_fields:
            objects = objects.filter(person_cluster=person_cluster)
        elif 'user' in model_fields:
            print(objects.first().user.customuser.person_cluster)
            objects = objects.filter(user__customuser__person_cluster=person_cluster)
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
@filter_person_cluster
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
    """
    model_name = request.GET.get('model')
    object_id = request.GET.get('id')
    
    # Check if model exists
    model, response = _check_model_exists(model_name)
    if response:
        return JsonResponse({'error': 'Model not found'}, status=404)
    
    if model_name == 'user':
        model = User
        object_id = CustomUser.objects.get(id=object_id).user.id
    
    
    # Get the object and check organization
    instance, response = _get_object_with_org_check(model, object_id, request)
    if isinstance(response, HttpResponse):
        return JsonResponse({'error': 'Object not found or access denied'}, status=403)
    
    # Use Django's collector to find objects that would be deleted
    from django.db.models.deletion import Collector
    from django.db import router
    
    collector = Collector(using=router.db_for_write(model))
    collector.collect([instance], keep_parents=False)

    # We don't want to include the object itself in the list
    for model_obj, instances in collector.data.items():
        if instance in instances:
            instances.remove(instance)
    
    # Format the related objects
    related_objects = []
    for model_obj, instances in collector.data.items():
        # Skip empty lists after removing the instance itself
        if not instances:
            continue
            
        for obj in instances:
            # Skip objects from other organizations for security
            # if hasattr(obj, 'org') and obj.org != request.user.org:
            #     continue
                
            # Get a display name for the object
            display_name = str(obj)
            
            # # Try to get a user-friendly name for the object
            # for field_name in ['name', 'title', 'username', 'ordner_name', 'titel']:
            #     if hasattr(obj, field_name) and getattr(obj, field_name):
            #         display_name = getattr(obj, field_name)
            #         break
            
            # # Handle user names specially
            # if hasattr(obj, 'first_name') and hasattr(obj, 'last_name'):
            #     if obj.first_name and obj.last_name:
            #         display_name = f"{obj.first_name} {obj.last_name}"
            
            # # Handle user relation
            # if hasattr(obj, 'user'):
            #     if hasattr(obj.user, 'first_name') and hasattr(obj.user, 'last_name'):
            #         if obj.user.first_name and obj.user.last_name:
            #             display_name = f"{obj.user.first_name} {obj.user.last_name}"
            
            related_objects.append({
                'id': obj.pk,
                'model': model_obj._meta.verbose_name,
                'display_name': display_name
            })
    
    return JsonResponse({
        'cascade_objects': related_objects
    })

def _get_ampel_matrix(request, users):
        # Get date range for ampel entries
    date_range = _get_ampel_date_range(request.user.org)
    start_date, end_date = date_range['start_date'], date_range['end_date']
    
    # Get ampel entries within date range
    ampel_entries = Ampel2.objects.filter(
        user__in=users,
        date__gte=start_date,
        date__lte=end_date
    ).order_by('user', 'date')
    
    # Generate month labels
    months = _generate_month_labels(start_date, end_date)
    
    # Create and fill ampel matrix
    ampel_matrix = _create_ampel_matrix(users, months, ampel_entries)
    
    # Group users by personen_cluster for template
    grouped_matrix = {}
    for user in users:
        if user.person_cluster not in grouped_matrix:
            grouped_matrix[user.person_cluster] = {}
        grouped_matrix[user.person_cluster][user] = ampel_matrix[user]

    return grouped_matrix, months

@login_required
@required_role('O')
@filter_person_cluster
def list_ampel(request):
    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        status = request.POST.get('status')
        comment = request.POST.get('comment')
        date_str = request.POST.get('date')

        try:
            user = User.objects.get(id=user_id)
            if user.customuser.org != request.user.org:
                messages.error(request, _('Nicht erlaubt'))
                return redirect('list_ampel')

            entry_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            entry_datetime = timezone.make_aware(datetime.combine(entry_date, timezone.now().time()))

            Ampel2.objects.create(
                org=request.user.org,
                user=user,
                status=status,
                comment=comment,
                date=entry_datetime
            )
            messages.success(request, _('Ampel-Eintrag erfolgreich hinzugefügt.'))
        except User.DoesNotExist:
            messages.error(request, _('Benutzer nicht gefunden.'))
        except Exception as e:
            messages.error(request, _('Ein Fehler ist aufgetreten: {}').format(e))
        
        return redirect('list_ampel')

    # Base queryset for freiwillige
    user_qs, person_cluster = get_filtered_user_queryset(request, 'ampel')
    error = None
    
    if not person_cluster or person_cluster.ampel:
        ampel_matrix, months = _get_ampel_matrix(request, user_qs)
    else:
        ampel_matrix = {}
        months = []
        error = f'{person_cluster.name} hat keine Ampel-Funktion aktiviert'
    
    context = {
        'months': months,
        'ampel_matrix': ampel_matrix,
        'current_month': timezone.now().strftime("%b %y"),
        'error': error,
        'today': timezone.now().date(),
    }
    return render(request, 'list_ampel.html', context=context)

def _get_ampel_date_range(org):
    """
    Helper function to determine the date range for ampel entries.
    
    Args:
        org: Organization instance
        
    Returns:
        dict: Contains 'start_date' and 'end_date' keys with date values
    """
    # Get organization's freiwillige users for efficient querying
    freiwillige_users = Freiwilliger.objects.filter(org=org).values_list('user', flat=True)
    
    # Get date range from freiwillige start/end dates
    freiwillige_dates = _get_freiwillige_date_range(org)
    
    # Get date range from ampel entries
    ampel_dates = _get_ampel_entry_date_range(freiwillige_users)
    
    # Combine and determine final date range
    start_date = _get_earliest_date([
        freiwillige_dates['start_date'],
        ampel_dates['start_date']
    ])
    
    end_date = _get_latest_date([
        freiwillige_dates['end_date'],
        ampel_dates['end_date']
    ])
    
    # Fallback to last 12 months if no valid dates found
    if not start_date or not end_date:
        end_date = timezone.now().date()
        start_date = end_date - relativedelta(months=12)
        
    return {
        'start_date': start_date,
        'end_date': end_date
    }


def _get_freiwillige_date_range(org):
    """Get the date range from freiwillige start and end dates."""
    start_dates = Freiwilliger.objects.filter(org=org).aggregate(
        real_start=Min('start_real'),
        planned_start=Min('start_geplant')
    )
    
    end_dates = Freiwilliger.objects.filter(org=org).aggregate(
        real_end=Max('ende_real'),
        planned_end=Max('ende_geplant')
    )
    
    return {
        'start_date': start_dates['real_start'] or start_dates['planned_start'],
        'end_date': end_dates['real_end'] or end_dates['planned_end']
    }


def _get_ampel_entry_date_range(freiwillige_users):
    """Get the date range from ampel entries for given users."""
    ampel_entries = Ampel2.objects.filter(user__in=freiwillige_users).order_by('date')
    
    first_entry = ampel_entries.first()
    last_entry = ampel_entries.last()
    
    return {
        'start_date': first_entry.date.date() if first_entry else None,
        'end_date': last_entry.date.date() if last_entry else None
    }


def _get_earliest_date(dates):
    """Get the earliest non-None date from a list of dates."""
    valid_dates = [date for date in dates if date is not None]
    return min(valid_dates) if valid_dates else None


def _get_latest_date(dates):
    """Get the latest non-None date from a list of dates."""
    valid_dates = [date for date in dates if date is not None]
    return max(valid_dates) if valid_dates else None

def _generate_month_labels(start_date, end_date):
    """
    Generate month labels between two dates.
    
    Args:
        start_date: Start date for the range
        end_date: End date for the range
        
    Returns:
        list: List of month labels in "MMM YY" format
    """
    if not start_date or not end_date:
        return []
        
    months = []
    current = start_date
    
    while current <= end_date:
        months.append(current.strftime("%b %y"))
        current += relativedelta(months=1)
    
    return months


def _create_ampel_matrix(freiwillige, months, ampel_entries):
    """
    Create and fill the ampel matrix with entries.
    
    Args:
        freiwillige: List of freiwillige users
        months: List of month labels
        ampel_entries: QuerySet of ampel entries
        
    Returns:
        dict: Matrix with freiwillige as keys and months as nested keys
    """
    # Initialize empty matrix
    matrix = {fw: {month: [] for month in months} for fw in freiwillige}
    
    # Fill matrix with ampel entries
    for entry in ampel_entries:
        month_key = entry.date.strftime("%b %y")
        if month_key in months and entry.user in freiwillige:
            matrix[entry.user][month_key].append({
                'status': entry.status,
                'comment': entry.comment,
                'date': entry.date.strftime("%d.%m.%y %H:%M")
            })
            
    return matrix

@login_required
@required_role('O')
@filter_person_cluster
def list_aufgaben_table(request, scroll_to=None):


    users, person_cluster = get_filtered_user_queryset(request, 'aufgaben')

    if not person_cluster or person_cluster.aufgaben:
        aufgaben = Aufgabe2.objects.filter(org=request.user.org)
        if person_cluster:
            aufgaben = aufgaben.filter(person_cluster=person_cluster).distinct()

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
            if person_cluster:
                aufgaben_cluster = aufgaben_cluster.filter(person_cluster=person_cluster)
            if aufgaben_cluster:
                aufgaben = aufgaben.filter(faellig_art__in=aufgaben_cluster)
                filter_type = aufgaben_cluster.first()


        # Instead of querying in loops
        user_aufgaben = UserAufgaben.objects.filter(
            org=request.user.org,
            user__in=users,
            aufgabe__in=aufgaben
        ).select_related('user', 'aufgabe').prefetch_related(
            Prefetch(
                'useraufgabenzwischenschritte_set',
                queryset=UserAufgabenZwischenschritte.objects.all(),
                to_attr='prefetched_zwischenschritte'
            )
        )

        # Create a lookup dictionary for faster access
        user_aufgaben_dict = {}
        for ua in user_aufgaben:
            if ua.user_id not in user_aufgaben_dict:
                user_aufgaben_dict[ua.user_id] = {}
            user_aufgaben_dict[ua.user_id][ua.aufgabe_id] = ua

        # Then modify your matrix building to use the dictionary
        user_aufgaben_matrix = {}
        for user in users:
            user_aufgaben_matrix[user] = []
            for aufgabe in aufgaben:
                ua = user_aufgaben_dict.get(user.id, {}).get(aufgabe.id, None)
                if ua:
                    zwischenschritte = ua.prefetched_zwischenschritte
                    zwischenschritte_count = len(zwischenschritte)
                    zwischenschritte_done_count = sum(1 for z in zwischenschritte if z.erledigt)
                    user_aufgaben_matrix[user].append({
                        'user_aufgabe': ua,
                        'zwischenschritte': zwischenschritte,
                        'zwischenschritte_done_open': f'{zwischenschritte_done_count}/{zwischenschritte_count}' if zwischenschritte_count > 0 else False,
                        'zwischenschritte_done': zwischenschritte_done_count == zwischenschritte_count and zwischenschritte_count > 0,
                    })
                elif user.person_cluster in aufgabe.person_cluster.all():
                    user_aufgaben_matrix[user].append(aufgabe.id)
                else:
                    user_aufgaben_matrix[user].append(None)

        # Get countries for users
        countries = Einsatzland2.objects.filter(org=request.user.org)

        aufgaben_cluster = AufgabenCluster.objects.filter(org=request.user.org)
        if person_cluster:
            aufgaben_cluster = aufgaben_cluster.filter(person_cluster=person_cluster)

        context = {
            'current_person_cluster': get_person_cluster(request),
            'users': users,
            'aufgaben': aufgaben,
            'today': date.today(),
            'user_aufgaben_matrix': user_aufgaben_matrix,
            'aufgaben_cluster': aufgaben_cluster,
            'filter': filter_type,
            'scroll_to': scroll_to,
            'countries': countries,
            'large_container': True
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
            response.set_cookie('filter_aufgaben_table', request.GET.get('f'), max_age=7 * 24 * 60 * 60)  # 7 days in seconds

    return response

@login_required
@required_role('O')
@filter_person_cluster
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
@filter_person_cluster
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
@filter_person_cluster
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
@required_role('O')
@filter_person_cluster
def download_aufgabe(request, id):
    try:
        aufgabe = UserAufgaben.objects.get(pk=id)
        if not aufgabe.org == request.user.org:
            return HttpResponse('Nicht erlaubt')
        if not aufgabe.file:
            return HttpResponse('Keine Datei gefunden')
        if not aufgabe.file.path:
            return HttpResponse('Datei nicht gefunden')
        if not os.path.exists(aufgabe.file.path):
            return HttpResponse('Datei nicht gefunden')
        
        if not aufgabe.file_downloaded_of.filter(id=request.user.id).exists():
            aufgabe.file_downloaded_of.add(request.user)
            aufgabe.save()
            
        response = HttpResponse(aufgabe.file.read(), content_type='application/octet-stream')
        response['Content-Disposition'] = f'attachment; filename="{aufgabe.file.name.replace(" ", "_")}"'

        return response
    except UserAufgaben.DoesNotExist:
        return HttpResponse('Nicht erlaubt')

@login_required
@required_role('O')
@filter_person_cluster
def statistik(request):
    field_name = request.GET.get('field')

    fields_types_for_stats = ['T', 'C', 'D', 'B']
    if not 'selectedPersonCluster' in request.COOKIES:
        fields_types_for_stats.append('E')

    if field_name:
        # Check if it's a UserAttribute field
        if Attribute.objects.filter(name=field_name, org=request.user.org).exists():
            attribute = Attribute.objects.get(name=field_name, org=request.user.org)
            
            if attribute.type not in fields_types_for_stats:
                return JsonResponse({'error': 'Invalid field'}, status=400)
            
            stats = UserAttribute.objects.filter(
                org=request.user.org,
                attribute=attribute,
                user__in=Freiwilliger.objects.filter(org=request.user.org).values('user')
            ).values('value').annotate(count=Count('id')).order_by('value')
            
            data = {str(item['value']) if item['value'] is not None else 'Nicht angegeben': item['count'] for item in stats}
            return JsonResponse(data)
        
        # Original code for Freiwilliger fields
        if field_name not in [f.name for f in Freiwilliger._meta.fields]:
            return JsonResponse({'error': 'Invalid field'}, status=400)
        
        stats = Freiwilliger.objects.filter(org=request.user.org)\
            .values(field_name)\
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
                key = str(value) if value is not None else 'Nicht angegeben'
            data[key] = item['count']
        
        return JsonResponse(data)

    freiwillige = Freiwilliger.objects.filter(org=request.user.org)
    filter_for_fields = ['einsatzland2', 'einsatzstelle2']
    if not 'selectedPersonCluster' in request.COOKIES:
        filter_for_fields.append('personen_cluster')
    
    # Get regular fields
    all_fields = Freiwilliger._meta.fields
    fields = [field for field in all_fields if field.name in filter_for_fields]
    
    # Get UserAttribute fields
    person_cluster = get_person_cluster(request)
    if person_cluster:
        attributes = Attribute.objects.filter(org=request.user.org, person_cluster=person_cluster, type__in=fields_types_for_stats)
    else:
        attributes = Attribute.objects.filter(org=request.user.org, type__in=fields_types_for_stats)
    
    # Convert attributes to field-like objects
    attribute_fields = [type('AttributeField', (), {
        'name': attr.name,
        'verbose_name': attr.name
    }) for attr in attributes]
    
    # Combine regular fields and attribute fields
    fields.extend(attribute_fields)
    
    return render(request, 'statistik.html', context={'freiwillige': freiwillige, 'fields': fields})

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
    
    # Standard case: redirect to list view with optional highlighting
    if object_id:
        return redirect('list_object_highlight', model_name=model_name, highlight_id=object_id)
    else:
        return redirect('list_object', model_name=model_name)
    
@login_required
@required_role('O')
@filter_person_cluster
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
@filter_person_cluster
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
@filter_person_cluster
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
@required_role('O')
def application_answer_download(request, bewerber_id):
    bewerber = get_object_or_404(Bewerber, id=bewerber_id, org=request.user.org)
    
    # Generate PDF using the new utils
    pdf_content = generate_full_application_pdf(bewerber)
    
    # Create filename
    filename = f"bewerbung_{bewerber.user.first_name}_{bewerber.user.last_name}_{datetime.now().strftime('%Y%m%d')}.pdf"
    filename = "".join(c for c in filename if c.isalnum() or c in (' ', '-', '_', '.')).rstrip()
    filename = filename.replace(' ', '_')
    
    return create_pdf_response(pdf_content, filename)

@login_required
@required_role('O')
def application_answer_download_fields(request, bewerber_id):
    bewerber = get_object_or_404(Bewerber, id=bewerber_id, org=request.user.org)
    
    # Get selected question IDs from request
    selected_question_ids = request.GET.getlist('questions')
    if not selected_question_ids:
        messages.error(request, 'Bitte wählen Sie mindestens eine Frage aus.')
        return redirect('application_detail', id=bewerber_id)
    
    # Generate PDF using the new utils
    pdf_content = generate_selected_application_pdf(bewerber, selected_question_ids)
    
    # Create filename
    filename = f"bewerbung_auswahl_{bewerber.user.last_name}_{datetime.now().strftime('%Y%m%d')}.pdf"
    filename = "".join(c for c in filename if c.isalnum() or c in (' ', '-', '_', '.')).rstrip()
    filename = filename.replace(' ', '_')
    
    return create_pdf_response(pdf_content, filename)

@login_required
@required_role('O')
@require_http_methods(["POST"])
def create_sticky_note(request):
    """Create a new sticky note."""
    notiz = request.POST.get('notiz')
    priority = request.POST.get('priority', 0)
    if not notiz:
        messages.error(request, 'Bitte geben Sie eine Notiz ein.')
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
        messages.error(request, 'Keine Notiz ID angegeben.')
        return redirect('org_home')
    
    try:
        notiz = StickyNote.objects.get(
            id=notiz_id,
            org=request.user.org,
            user=request.user
        )
        notiz.delete()
    except StickyNote.DoesNotExist:
        messages.error(request, 'Notiz konnte nicht gefunden werden.')
    
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
        return None, JsonResponse({'success': False, 'error': 'Task not found'}, status=404)

def _get_aufgabe_with_org_check(aufgabe_id, org):
    """Get Aufgabe2 with organization check."""
    try:
        return Aufgabe2.objects.get(id=aufgabe_id, org=org), None
    except Aufgabe2.DoesNotExist:
        return None, JsonResponse({'success': False, 'error': 'Task not found'}, status=404)

def _get_user_with_org_check(user_id, org):
    """Get User with organization check."""
    try:
        user = User.objects.get(id=user_id)
        if user.customuser.org != org:
            return None, JsonResponse({'success': False, 'error': 'User not found'}, status=404)
        return user, None
    except User.DoesNotExist:
        return None, JsonResponse({'success': False, 'error': 'User not found'}, status=404)

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
        
        # Get aufgabe and check organization
        aufgabe, error_response = _get_aufgabe_with_org_check(aufgabe_id, request.user.org)
        if error_response:
            return error_response
        
        # Get all eligible users
        users, person_cluster = get_filtered_user_queryset(request, 'aufgaben')
        users = users.filter(customuser__person_cluster__in=aufgabe.person_cluster.all())
        
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
    }, {
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
    }
    ]
    
    return render(request, 'copy_links.html', {'page_elements': page_elements})