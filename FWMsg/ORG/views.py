from datetime import date, datetime, timedelta
import io
import os
import zipfile
import pandas as pd
import subprocess
import json

from django.db.models import ForeignKey
from django.shortcuts import render, redirect
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
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

from Global.models import (
    Attribute, AufgabenCluster, Freiwilliger2, Aufgabe2, Maintenance, PersonCluster, UserAttribute, 
    UserAufgaben, Post2, Bilder2, CustomUser,
    BilderGallery2, Ampel2, ProfilUser2, Notfallkontakt2,
    Einsatzland2, Einsatzstelle2,
    AufgabeZwischenschritte2, UserAufgabenZwischenschritte
)
from TEAM.models import Team
from django.contrib.auth.models import User

from django.db import models
import ORG.forms as ORGforms
from FWMsg.decorators import required_role
from django.views.decorators.http import require_http_methods

base_template = 'baseOrg.html'

class PersonenClusterFilteredQuerySet(QuerySet):
    """Custom QuerySet that automatically filters by personen_cluster from cookie."""
    def __init__(self, *args, **kwargs):
        self._personen_cluster_id = None
        super().__init__(*args, **kwargs)

    def set_person_cluster_id(self, person_cluster_id):
        self._personen_cluster_id = person_cluster_id
        return self

    def _clone(self):
        clone = super()._clone()
        clone._person_cluster_id = self._person_cluster_id
        return clone

    def filter(self, *args, **kwargs):
        queryset = super().filter(*args, **kwargs)
        if self._person_cluster_id and self.model == Freiwilliger2:
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

        original_get_queryset_freiwilliger = Freiwilliger2.objects.get_queryset
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
    
        Freiwilliger2.objects.get_queryset = get_person_cluster_queryset.__get__(Freiwilliger2.objects)
        Aufgabe2.objects.get_queryset = get_person_cluster_queryset_aufgabe.__get__(Aufgabe2.objects)
        #CustomUser.objects.get_queryset = get_person_cluster_queryset_user.__get__(CustomUser.objects)

        try:
            return view_func(request, *args, **kwargs)
        finally:
            Freiwilliger2.objects.get_queryset = original_get_queryset_freiwilliger
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
    if hasattr(request, 'user') and request.user.is_authenticated and (request.user.customuser.person_cluster.view == 'O' or request.user.customuser.person_cluster.view == 'T'):
        return {
            'person_cluster': PersonCluster.objects.filter(org=request.user.org)
        }
    return {}

allowed_models_to_edit = {
    'einsatzland': Einsatzland2,
    'einsatzstelle': Einsatzstelle2,
    'freiwilliger': Freiwilliger2,
    'attribute': Attribute,
    'aufgabe': Aufgabe2,
    'notfallkontakt': Notfallkontakt2,
    'freiwilligeraufgaben': UserAufgaben,
    'team': Team,
    'user': CustomUser,
    'personcluster': PersonCluster
}


# Create your views here.
@login_required
@required_role('O')
@filter_person_cluster
def home(request):
    from Global.views import get_bilder

    # Get latest images
    latest_images = Bilder2.objects.filter(
        org=request.user.org
    ).order_by('-date_created')[:6]  # Show last 6 images

    # Get all gallery images and group by bilder
    gallery_images = get_bilder(request.user.org)[:6]

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

    context = {
        'gallery_images': gallery_images,
        'pending_tasks': pending_tasks,
        'open_tasks': open_tasks
    }
    
    return render(request, 'homeOrg.html', context)


@staff_member_required
def nginx_statistic(request):
    try:
        # Path to the pre-generated HTML file
        report_path = '/home/fwmsg/tmp/report.html'
        
        # Read the HTML file
        with open(report_path, 'r', encoding='utf-8') as file:
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


def get_model(model_name):
    if model_name in allowed_models_to_edit:
        return allowed_models_to_edit[model_name]
    return None


@login_required
@required_role('O')
@filter_person_cluster
def save_form(request, form):
    obj = form.save(commit=False)
    obj.org = request.user.org
    obj.save()
    form.save_m2m()
    if hasattr(form, 'zwischenschritte'):
        for form in form.zwischenschritte.forms:
            if form.cleaned_data and not form.cleaned_data.get('DELETE', False):
                zwischenschritt = form.save(commit=False)
                zwischenschritt.org = request.user.org
                zwischenschritt.save()


@login_required
@required_role('O')
@filter_person_cluster
def add_object(request, model_name):
    freiwilliger_id = request.GET.get('freiwilliger')
    aufgabe_id = request.GET.get('aufgabe')
    if freiwilliger_id and aufgabe_id:
        freiwilliger = Freiwilliger2.objects.get(pk=freiwilliger_id)
        aufgabe = Aufgabe2.objects.get(pk=aufgabe_id)

        if not freiwilliger.org == request.user.org or not aufgabe.org == request.user.org:
            return HttpResponse('Nicht erlaubt')

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
        model = get_model(model_name)

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
    model = get_model(model_name.lower())
    if not model or not model in ORGforms.model_to_form_mapping:
        return HttpResponse(f'Kein Formular für {model_name} gefunden')

    if not id == None:
        instance = get_object_or_404(model, id=id)
        if not instance.org == request.user.org:
            return HttpResponse('Nicht erlaubt')

        form = ORGforms.model_to_form_mapping[model](
            request.POST or None,
            request.FILES or None,
            instance=instance,
            request=request  # Pass request to form
        )
    else:
        form = ORGforms.model_to_form_mapping[model](
            request.POST or None,
            request.FILES or None,
            request=request  # Pass request to form
        )

    if form.is_valid():
        save_form(request, form)
        obj = form.instance.id
        highlight_id = obj

        next = request.GET.get('next')
        if next:
            return redirect(next)

        if model_name == 'freiwilligeraufgaben':
            return redirect('list_aufgaben_table')
        
        return redirect('list_object_highlight', model_name=model_name, highlight_id=highlight_id)

    return render(request, 'edit_object.html', {'form': form, 'object': model_name})


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
    model = get_model(model_name)

    if not model:
        return HttpResponse(f'Kein Model für {model_name} gefunden')

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
        objects = filter_objects(objects)
        objects = objects.order_by('user__first_name', 'user__last_name')

        objects = extend_fields(objects, field_metadata, model_fields, user_fields, position=0)

    elif model._meta.object_name == 'Freiwilliger' or model._meta.object_name == 'Referenten':
        objects = objects.order_by('user__first_name', 'user__last_name')
        
        objects = extend_fields(objects, field_metadata, model_fields, user_fields, 0)

        attributes = []
        if person_cluster:
            attributes = Attribute.objects.filter(org=request.user.org, person_cluster=person_cluster)
            if not person_cluster.view == 'F' and model._meta.object_name == 'Freiwilliger':
                error = f'{person_cluster.name} sind keine Freiwillige'
            elif not person_cluster.view == 'T' and model._meta.object_name == 'Referenten':
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
    
    return render(request, 'list_objects.html',
                 {'objects': objects, 
                  'field_metadata': field_metadata, 
                  'model_name': model_name,
                  'verbose_name': model._meta.verbose_name_plural,
                  'filter_form': filter_form,
                  'highlight_id': highlight_id,
                  'error': error})


@login_required
@required_role('O')
@filter_person_cluster
def delete_object(request, model_name, id):
    model = get_model(model_name)
    if not model:
        return HttpResponse(f'Kein Model für {model_name} gefunden')

    instance = get_object_or_404(model, id=id)
    if not instance.org == request.user.org:
        return HttpResponse('Nicht erlaubt')

    instance.delete()

    next = request.GET.get('next')
    if next:
        return redirect(next)
    
    return redirect('list_object', model_name=model_name)

def _get_ampel_matrix(request, users):
        # Get date range for ampel entries
    date_range = get_ampel_date_range(request.user.org)
    start_date, end_date = date_range['start_date'], date_range['end_date']
    
    # Get ampel entries within date range
    ampel_entries = Ampel2.objects.filter(
        user__in=users,
        date__gte=start_date,
        date__lte=end_date
    ).order_by('user', 'date')
    
    # Generate month labels
    months = generate_month_labels(start_date, end_date)
    
    # Create and fill ampel matrix
    ampel_matrix = create_ampel_matrix(users, months, ampel_entries)
    
    # Group users by personen_cluster for template
    grouped_matrix = {}
    for user in users:
        if user.customuser.person_cluster not in grouped_matrix:
            grouped_matrix[user.customuser.person_cluster] = {}
        grouped_matrix[user.customuser.person_cluster][user] = ampel_matrix[user]

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

def get_ampel_date_range(org):
    """Helper function to determine the date range for ampel entries."""
    # Get earliest start date
    start_dates = Freiwilliger2.objects.filter(org=org).aggregate(
        real_start=Min('start_real'),
        planned_start=Min('start_geplant')
    )
    start_date = start_dates['real_start'] or start_dates['planned_start']

    # Get latest end date
    end_dates = Freiwilliger2.objects.filter(org=org).aggregate(
        real_end=Max('ende_real'),
        planned_end=Max('ende_geplant')
    )
    end_date = end_dates['real_end'] or end_dates['planned_end']
    
    # Fallback to last 12 months if no dates found
    if not start_date or not end_date:
        end_date = timezone.now()
        start_date = end_date - relativedelta(months=12)
        
    return {'start_date': start_date, 'end_date': end_date}

def generate_month_labels(start_date, end_date):
    """Helper function to generate month labels between two dates."""
    months = []
    current = start_date
    while current <= end_date:
        months.append(current.strftime("%b %y"))
        current += relativedelta(months=1)
    return months

def create_ampel_matrix(freiwillige, months, ampel_entries):
    """Helper function to create and fill the ampel matrix."""
    # Initialize empty matrix
    matrix = {fw: {month: [] for month in months} for fw in freiwillige}
    
    # Fill matrix with ampel entries
    for entry in ampel_entries:
        month_key = entry.date.strftime("%b %y")
        if month_key in months:
            matrix[entry.freiwilliger][month_key].append({
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

        user_aufgabe = None
        
        for user in users:
            if not user.org == request.user.org or not aufgabe.org == request.user.org:
                continue
                
            if aufgabe.person_cluster and user.customuser.person_cluster and not user.customuser.person_cluster in aufgabe.person_cluster.all():
                name = f'{user.first_name + " " if user.first_name else ""}{user.last_name + " " if user.last_name else ""}{user.username if not user.first_name and not user.last_name else ""}'
                message = f'{name} ({user.customuser.person_cluster.name}) hat keine Aufgabe {aufgabe.name}'
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
        print(request.POST)
        country_id = request.POST.get('country_id')
        delete_file_of_aufgabe = request.POST.get('delete_file_of_aufgabe')

        if not UserAufgaben.objects.filter(pk=aufgabe_id, org=request.user.org).exists():
            return redirect('list_aufgaben_table_scroll', scroll_to=user_aufgabe.id)
        else:
            user_aufgabe = UserAufgaben.objects.get(pk=aufgabe_id, org=request.user.org)

        if request.POST.get('reminder') == 'True':
            user_aufgabe.send_reminder_email()
        elif country_id:
            users = User.objects.filter(org=request.user.org, einsatzland=country_id)
            aufgabe = Aufgabe2.objects.get(pk=aufgabe_id)
            for user in users:
                user_aufgabe, created = UserAufgaben.objects.get_or_create(
                    org=request.user.org,
                    user=user,
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
        if person_cluster:
            aufgaben = Aufgabe2.objects.filter(org=request.user.org, person_cluster=person_cluster).distinct()
        else:
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
        if filter_type and filter_type != 'None':
            aufgaben = aufgaben.filter(faellig_art=filter_type)

        user_aufgaben_matrix = {}
        for user in users:
            user_aufgaben_matrix[user] = []
            for aufgabe in aufgaben:
                user_aufgaben_exists = UserAufgaben.objects.filter(user=user, aufgabe=aufgabe).exists()
                if user_aufgaben_exists:
                    user_aufgabe = UserAufgaben.objects.get(user=user, aufgabe=aufgabe)
                    zwischenschritte = UserAufgabenZwischenschritte.objects.filter(user_aufgabe=user_aufgabe)
                    zwischenschritte_count = zwischenschritte.count()
                    zwischenschritte_done_count = zwischenschritte.filter(erledigt=True).count()
                    user_aufgaben_matrix[user].append({
                        'user_aufgabe': user_aufgabe,
                        'zwischenschritte': zwischenschritte,
                        'zwischenschritte_done_open': f'{zwischenschritte_done_count}/{zwischenschritte_count}' if zwischenschritte_count > 0 else False,
                        'zwischenschritte_done': zwischenschritte_done_count == zwischenschritte_count and zwischenschritte_count > 0,
                    })
                elif user.customuser.person_cluster in aufgabe.person_cluster.all():
                    user_aufgaben_matrix[user].append(aufgabe.id)
                else:
                    user_aufgaben_matrix[user].append(None)

        # Get countries for users
        countries = Einsatzland2.objects.filter(org=request.user.org)

        context = {
            'current_person_cluster': get_person_cluster(request),
            'users': users,
            'aufgaben': aufgaben,
            'today': date.today(),
            'user_aufgaben_matrix': user_aufgaben_matrix,
            'aufgaben_cluster': AufgabenCluster.objects.filter(org=request.user.org),
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
            response.set_cookie('filter_aufgaben_table', request.GET.get('f'))

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


@login_required
@required_role('O')
@filter_person_cluster
def list_bilder(request):
    bilder = Bilder2.objects.filter(org=request.user.org)

    gallery_images = {}

    for bild in bilder:
        gallery_images[bild] = BilderGallery2.objects.filter(bilder=bild)

    return render(request, 'list_bilder.html', context={'gallery_images': gallery_images})


@login_required
@required_role('O')
@filter_person_cluster
def download_bild_as_zip(request, id):
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


@login_required
@required_role('O')
@filter_person_cluster
def dokumente(request):
    return render(request, 'dokumente.html', context={'extends_base': base_template})


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
                user__in=Freiwilliger2.objects.filter(org=request.user.org).values('user')
            ).values('value').annotate(count=Count('id')).order_by('value')
            
            data = {str(item['value']) if item['value'] is not None else 'Nicht angegeben': item['count'] for item in stats}
            return JsonResponse(data)
        
        # Original code for Freiwilliger fields
        if field_name not in [f.name for f in Freiwilliger2._meta.fields]:
            return JsonResponse({'error': 'Invalid field'}, status=400)
        
        stats = Freiwilliger2.objects.filter(org=request.user.org)\
            .values(field_name)\
            .annotate(count=Count('id'))\
            .order_by(field_name)
        
        # Convert QuerySet to dictionary
        data = {}
        for item in stats:
            value = item[field_name]
            if isinstance(value, int) and any(f.name == field_name and isinstance(f, ForeignKey) for f in Freiwilliger2._meta.fields):
                related_obj = Freiwilliger2._meta.get_field(field_name).related_model.objects.get(id=value)
                key = str(related_obj)
            else:
                key = str(value) if value is not None else 'Nicht angegeben'
            data[key] = item['count']
        
        return JsonResponse(data)

    freiwillige = Freiwilliger2.objects.filter(org=request.user.org)
    filter_for_fields = ['einsatzland', 'einsatzstelle', 'kirchenzugehoerigkeit', 'geschlecht', 'ort', 'geburtsdatum']
    if not 'selectedPersonCluster' in request.COOKIES:
        filter_for_fields.append('personen_cluster')
    
    # Get regular fields
    all_fields = Freiwilliger2._meta.fields
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