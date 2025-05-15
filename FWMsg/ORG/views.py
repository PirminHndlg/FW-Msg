from datetime import date, datetime, timedelta
import io
import os
import zipfile
import pandas as pd
import subprocess
import json

from django.db.models import ForeignKey
from django.shortcuts import render, redirect
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse, Http404, HttpResponseNotAllowed, HttpResponseNotFound
from django.shortcuts import get_object_or_404
from django.db.models import Max, F, Min
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings
from functools import wraps
from dateutil.relativedelta import relativedelta
from django.utils import timezone
from django.template.context_processors import request
from django.db.models import QuerySet, Subquery, OuterRef
from django.db.models import Case, When, Value, Count, Q
from django.contrib.admin.views.decorators import staff_member_required
from django.template.loader import render_to_string
from django.db.models.query import Prefetch
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

from Global.models import (
    Attribute, AufgabenCluster, Aufgabe2, KalenderEvent, Maintenance, PersonCluster, UserAttribute, 
    UserAufgaben, Post2, Bilder2, CustomUser,
    BilderGallery2, Ampel2, ProfilUser2, Notfallkontakt2,
    Einsatzland2, Einsatzstelle2,
    AufgabeZwischenschritte2, UserAufgabenZwischenschritte
)
from TEAM.models import Team
from FW.models import Freiwilliger
from django.contrib.auth.models import User

from django.db import models
import ORG.forms as ORGforms
from FWMsg.decorators import required_role
from django.views.decorators.http import require_http_methods

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
    if hasattr(request, 'user') and request.user.is_authenticated and (request.user.role == 'O' or request.user.role == 'T'):
        return {
            'person_cluster': PersonCluster.objects.filter(org=request.user.org)
        }
    return {}

allowed_models_to_edit = {
    'einsatzland': Einsatzland2,
    'einsatzstelle': Einsatzstelle2,
    'freiwilliger': Freiwilliger,
    'attribute': Attribute,
    'aufgabe': Aufgabe2,
    'notfallkontakt': Notfallkontakt2,
    'useraufgaben': UserAufgaben,
    'team': Team,
    'user': CustomUser,
    'personcluster': PersonCluster,
    'aufg-filter': AufgabenCluster,
    'kalender': KalenderEvent
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

    context = {
        'gallery_images': gallery_images,
        'pending_tasks': pending_tasks,
        'open_tasks': open_tasks,
        'my_open_tasks': my_open_tasks,
        'posts': posts
    }
    
    return render(request, 'homeOrg.html', context)


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

    return render(request, 'edit_object.html', {'form': form, 'object': model_name, 'verbose_name': model._meta.verbose_name})


def _check_filter_form(filter_form, model, objects):
    # Apply filters if form is valid
    if filter_form.is_valid():
        # Handle search across all text fields
        search_query = filter_form.cleaned_data.get('search')
        if search_query:
            search_filters = models.Q()
            for field in model._meta.fields:
                if isinstance(field, (models.CharField, models.TextField)):
                    search_filters |= models.Q(**{f'{field.name}__icontains': search_query})
            objects = objects.filter(search_filters)
        
        # Apply specific field filters
        for field in model._meta.fields:
            if field.name in ['org', 'id']:
                continue
                
            if isinstance(field, (models.CharField, models.TextField)):
                value = filter_form.cleaned_data.get(f'filter_{field.name}')
                if value:
                    objects = objects.filter(**{f'{field.name}__icontains': value})
                    
            elif isinstance(field, (models.BooleanField)):
                value = filter_form.cleaned_data.get(f'filter_{field.name}')
                if value:  # Only apply filter if a value is selected
                    objects = objects.filter(**{field.name: value == 'true'})
                    
            elif isinstance(field, models.DateField):
                date_from = filter_form.cleaned_data.get(f'filter_{field.name}_from')
                date_to = filter_form.cleaned_data.get(f'filter_{field.name}_to')
                if date_from:
                    objects = objects.filter(**{f'{field.name}__gte': date_from})
                if date_to:
                    objects = objects.filter(**{f'{field.name}__lte': date_to})
                    
            elif isinstance(field, models.ForeignKey):
                value = filter_form.cleaned_data.get(f'filter_{field.name}')
                if value:
                    objects = objects.filter(**{field.name: value})

@login_required
@required_role('O')
@filter_person_cluster
def list_object(request, model_name, highlight_id=None):
    # Check if model exists using the helper function
    model, response = _check_model_exists(model_name)
    if response:
        return response

    # Start with all objects for this organization
    objects = model.objects.filter(org=request.user.org)
    
    # Initialize the filter form
    filter_form = ORGforms.FilterForm(model, request.GET, request=request)
    # Apply filters if form is valid
    _check_filter_form(filter_form, model, objects)
    
    error = None
   
    field_metadata = [
        {'name': field.name, 'verbose_name': field.verbose_name}
        for field in model._meta.fields if field.name != 'org' and field.name != 'id' #and (field.name != 'user' or model._meta.object_name == 'CustomUser')
    ]

    model_fields = [field.name for field in model._meta.fields]

    person_cluster = get_person_cluster(request)

    def check_person_cluster(field_name):
        if person_cluster:
            if not getattr(person_cluster, field_name):
                error = f'{person_cluster.name} hat keine {field_name[0].upper() + field_name[1:].replace("_", " ")}-Funktion aktiviert'
                return error
        return None

    def filter_objects(objects, filter_name=None):
        if person_cluster:
            if filter_name == 'usr_aufg':
                objects = objects.filter(aufgabe__person_cluster=person_cluster)
            else:
                objects = objects.filter(person_cluster=person_cluster)
        return objects

    def extend_fields(objects, field_metadata, model_fields, fields, position=None):
        if position == 0:
            field_metadata[0:0] = fields
            model_fields[0:0] = [field['name'] for field in fields]
            objects = objects.annotate(
                **{field['name']: F(f'user__{field["name"].replace("user_", "")}') for field in fields}
            )
        else:
            field_metadata.extend(fields)
            model_fields.extend(field['name'] for field in fields)
            objects = objects.annotate(
                **{field['name']: F(f'user__{field["name"].replace("user_", "")}') for field in fields}
            )
        return objects

    user_fields = [
        {'name': 'user_first_name', 'verbose_name': 'Vorname', 'type': 'T'},
        {'name': 'user_last_name', 'verbose_name': 'Nachname', 'type': 'T'},
        {'name': 'user_email', 'verbose_name': 'Email', 'type': 'E'}
    ]    

    if model._meta.object_name == 'Aufgabe':
        error = check_person_cluster('aufgaben')
        objects = filter_objects(objects)

        objects = objects.order_by('faellig_art', 'faellig_tag', 'faellig_monat', 'faellig_tage_nach_start', 'faellig_tage_vor_ende')
    
    elif model._meta.object_name == 'UserAufgaben':
        error = check_person_cluster('aufgaben')
        objects = filter_objects(objects, 'usr_aufg')

    elif model._meta.object_name == 'CustomUser':
        #remove field mail_notifications_unsubscribe_auth_key from objects and model_fields
        model._meta.fields = [field for field in model._meta.fields if field.name != 'mail_notifications_unsubscribe_auth_key']
        model_fields = [field.name for field in model._meta.fields]
        objects = objects.exclude(mail_notifications_unsubscribe_auth_key__isnull=False)
        
        objects = filter_objects(objects)
        objects = objects.order_by('user__first_name', 'user__last_name')
        
        objects = extend_fields(objects, field_metadata, model_fields, user_fields, position=0)
        
        user_fields = [
            {'name': 'user_last_login', 'verbose_name': 'Letzter Login', 'type': 'D'}
        ]
        objects = extend_fields(objects, field_metadata, model_fields, user_fields)

    elif model._meta.object_name == 'Freiwilliger' or model._meta.object_name == 'Team':
        objects = objects.order_by('user__first_name', 'user__last_name')
        
        objects = extend_fields(objects, field_metadata, model_fields, user_fields, 0)

        attributes = []
        if person_cluster:
            attributes = Attribute.objects.filter(org=request.user.org, person_cluster=person_cluster)
            if not person_cluster.view == 'F' and model._meta.object_name == 'Freiwilliger':
                error = f'{person_cluster.name} sind keine Freiwillige'
            elif not person_cluster.view == 'T' and model._meta.object_name == 'Team':
                error = f'{person_cluster.name} sind keine Teammitglieder'

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
                        org=request.user.org
                    ).values('value')[:1]
                )
            })

        # Order objects by user name
        objects = objects.order_by('user__first_name', 'user__last_name')
    
    elif model._meta.object_name == 'Notfallkontakt':
        person_cluster = get_person_cluster(request)
        if person_cluster:
            objects = objects.filter(user__customuser__person_cluster=person_cluster)
            if not person_cluster.notfallkontakt:
                error = f'{person_cluster.name} hat keine Notfallkontakt-Funktion aktiviert'

    else:
        if 'freiwilliger' in model_fields:
            objects = objects.order_by('freiwilliger__first_name', 'freiwilliger__last_name')
        elif 'first_name' in model_fields:
            objects = objects.order_by('first_name')
        elif 'last_name' in model_fields:
            objects = objects.order_by('last_name')
        elif 'name' in model_fields:
            objects = objects.order_by('name')
        else:
            objects = objects.order_by('id')
    
    # Add many-to-many fields
    m2m_fields = [
        {'name': field.name, 'verbose_name': field.verbose_name}
        for field in model._meta.many_to_many
    ]
    field_metadata.extend(m2m_fields)
    
    # Count total objects before pagination for display
    total_objects_count = objects.count()
    
    # Implement pagination
    page = request.GET.get('page', 1)
    items_per_page = 50  # You can make this configurable
    paginator = Paginator(objects, items_per_page)
    
    try:
        paginated_objects = paginator.page(page)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page
        paginated_objects = paginator.page(1)
    except EmptyPage:
        # If page is out of range, deliver last page
        paginated_objects = paginator.page(paginator.num_pages)
    
    # Create query parameters for pagination links
    query_params = request.GET.copy()
    if 'page' in query_params:
        del query_params['page']
    query_string = query_params.urlencode()
    
    return render(request, 'list_objects.html',
                 {'objects': paginated_objects, 
                  'field_metadata': field_metadata, 
                  'model_name': model_name,
                  'verbose_name': model._meta.verbose_name_plural,
                  'filter_form': filter_form,
                  'highlight_id': highlight_id,
                  'error': error,
                  'paginator': paginator,
                  'page_obj': paginated_objects,
                  'total_count': total_objects_count,
                  'query_string': query_string})


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
        'error': error
    }
    return render(request, 'list_ampel.html', context=context)

def _get_ampel_date_range(org):
    """Helper function to determine the date range for ampel entries."""
    # Get earliest start date
    start_dates = Freiwilliger.objects.filter(org=org).aggregate(
        real_start=Min('start_real'),
        planned_start=Min('start_geplant')
    )
    start_date = start_dates['real_start'] or start_dates['planned_start']

    # Get latest end date
    end_dates = Freiwilliger.objects.filter(org=org).aggregate(
        real_end=Max('ende_real'),
        planned_end=Max('ende_geplant')
    )
    end_date = end_dates['real_end'] or end_dates['planned_end']
    
    # Fallback to last 12 months if no dates found
    if not start_date or not end_date:
        end_date = timezone.now()
        start_date = end_date - relativedelta(months=12)
        
    return {'start_date': start_date, 'end_date': end_date}

def _generate_month_labels(start_date, end_date):
    """Helper function to generate month labels between two dates."""
    months = []
    current = start_date
    while current <= end_date:
        months.append(current.strftime("%b %y"))
        current += relativedelta(months=1)
    return months

def _create_ampel_matrix(freiwillige, months, ampel_entries):
    """Helper function to create and fill the ampel matrix."""
    # Initialize empty matrix
    matrix = {fw: {month: [] for month in months} for fw in freiwillige}
    
    # Fill matrix with ampel entries
    for entry in ampel_entries:
        month_key = entry.date.strftime("%b %y")
        if month_key in months:
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
    if request.method == 'GET' and request.GET.get('u') and request.GET.get('a'):
        user_id = request.GET.get('u')
        aufgabe_id = request.GET.get('a')

        if user_id == 'all':
            users, person_cluster = get_filtered_user_queryset(request, 'aufgaben')
        else:
            users = User.objects.filter(id=user_id)

        aufgabe = Aufgabe2.objects.get(pk=aufgabe_id)
        users = users.filter(customuser__person_cluster__in=aufgabe.person_cluster.all())

        user_aufgabe = None
        
        for user in users:
            if not user.org == request.user.org or not aufgabe.org == request.user.org:
                continue
                
            if aufgabe.person_cluster and user.person_cluster and not user.person_cluster in aufgabe.person_cluster.all():
                name = f'{user.first_name + " " if user.first_name else ""}{user.last_name + " " if user.last_name else ""}{user.username if not user.first_name and not user.last_name else ""}'
                message = f'{name} ({user.person_cluster.name}) hat keine Aufgabe {aufgabe.name}'
                messages.error(request, message)
                continue

            user_aufgabe, created = UserAufgaben.objects.get_or_create(
                org=request.user.org,
                user=user,
                aufgabe=aufgabe
            )

        if user_aufgabe:
            return redirect('list_aufgaben_table_scroll', scroll_to=user_aufgabe.id)
        else:
            return redirect('list_aufgaben_table')

    
    if request.method == 'POST':
        aufgabe_id = request.POST.get('aufgabe_id')
        country_id = request.POST.get('country_id')
        delete_file_of_aufgabe = request.POST.get('delete_file_of_aufgabe')

        if not UserAufgaben.objects.filter(pk=aufgabe_id, org=request.user.org).exists():
            return redirect('list_aufgaben_table_scroll', scroll_to=user_aufgabe.id)
        else:
            user_aufgabe = UserAufgaben.objects.get(pk=aufgabe_id, org=request.user.org)

        if request.POST.get('reminder') == 'True':
            user_aufgabe.send_reminder_email()
        elif country_id:
            aufgabe = Aufgabe2.objects.get(pk=aufgabe_id)
            users, _ = get_filtered_user_queryset(request, 'aufgaben')
            custom_users = CustomUser.objects.filter(org=request.user.org, user__in=users, person_cluster__in=aufgabe.person_cluster.all())
            for custom_user in custom_users:
                if (Freiwilliger.objects.filter(org=request.user.org, user=custom_user.user, einsatzland2=country_id).exists() or Team.objects.filter(org=request.user.org, user=custom_user.user, land=country_id).exists()):
                    user_aufgabe, created = UserAufgaben.objects.get_or_create(
                        org=request.user.org,
                        user=custom_user.user,
                        aufgabe=aufgabe
                    )
        elif delete_file_of_aufgabe and UserAufgaben.objects.filter(pk=delete_file_of_aufgabe, org=request.user.org).exists():
            user_aufgabe.file.delete()
            user_aufgabe.save()
            return redirect('list_aufgaben_table_scroll', scroll_to=user_aufgabe.id)
        else:
            user_aufgabe.pending = request.POST.get('pending') == 'True'
            user_aufgabe.erledigt = request.POST.get('erledigt') == 'True'
            user_aufgabe.erledigt_am = timezone.now() if user_aufgabe.erledigt else None
            user_aufgabe.save()
        return redirect('list_aufgaben_table_scroll', scroll_to=user_aufgabe.id)

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
            'countries': countries
        }
    
    else:
        context = {
            'error': f'{person_cluster.name} hat keine Aufgaben-Funktion aktiviert'
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
        
        response = HttpResponse(aufgabe.file.read(), content_type='application/octet-stream')
        response['Content-Disposition'] = f'attachment; filename="{aufgabe.file.name.replace(" ", "_")}"'

        return response
    except UserAufgaben.DoesNotExist:
        return HttpResponse('Nicht erlaubt')


@login_required
@required_role('O')
@filter_person_cluster
def download_bild_as_zip(request, id):
    try:
        bild = Bilder2.objects.get(pk=id)
        if not bild.org == request.user.org:
            return HttpResponse('Nicht erlaubt')
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zipf:
            for i, bild_gallery in enumerate(BilderGallery2.objects.filter(bilder=bild)):
                zipf.write(bild_gallery.image.path, f"{bild.user.username}-{bild.titel.replace(' ', '_')}-{bild.date_created.strftime('%Y-%m-%d')}_{i}{os.path.splitext(bild_gallery.image.path)[1]}")
        zip_buffer.seek(0)
        response = HttpResponse(zip_buffer, content_type='application/zip')
        response['Content-Disposition'] = f'attachment; filename="{bild.user.username}_{bild.titel}_{bild.date_created.strftime("%Y-%m-%d")}.zip"'
        return response
    except Bilder2.DoesNotExist:
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
    filter_for_fields = ['einsatzland', 'einsatzstelle', 'kirchenzugehoerigkeit', 'geschlecht', 'ort', 'geburtsdatum']
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