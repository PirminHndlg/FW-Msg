from datetime import date, datetime, timedelta
import io
import os
import zipfile
import pandas as pd

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
from django.db.models import QuerySet
from django.db.models import Case, When, Value, Count

from FW import models as FWmodels
from Global import models as Globalmodels
from . import models as ORGmodels
from . import forms as ORGforms

from FWMsg.decorators import required_role

base_template = 'baseOrg.html'

class JahrgangFilteredQuerySet(QuerySet):
    """Custom QuerySet that automatically filters by jahrgang from cookie."""
    def __init__(self, *args, **kwargs):
        self._jahrgang_id = None
        super().__init__(*args, **kwargs)

    def set_jahrgang_id(self, jahrgang_id):
        self._jahrgang_id = jahrgang_id
        return self

    def _clone(self):
        clone = super()._clone()
        clone._jahrgang_id = self._jahrgang_id
        return clone

    def filter(self, *args, **kwargs):
        queryset = super().filter(*args, **kwargs)
        if self._jahrgang_id and self.model == FWmodels.Freiwilliger:
            queryset = queryset.filter(jahrgang=self._jahrgang_id)
        return queryset
    

def filter_jahrgang(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        jahrgang_id = request.COOKIES.get('selectedJahrgang')
        if jahrgang_id and not FWmodels.Jahrgang.objects.filter(id=jahrgang_id, org=request.user.org).exists():
            jahrgang_id = None
            response = HttpResponseRedirect(request.META.get('HTTP_REFERER', '/'))
            if 'selectedJahrgang' in request.COOKIES:
                response.delete_cookie('selectedJahrgang')
            if 'selectedJahrgangName' in request.COOKIES:
                response.delete_cookie('selectedJahrgangName')
            return response

        original_get_queryset = FWmodels.Freiwilliger.objects.get_queryset

        def get_jahrgang_queryset(manager):
            base_qs = original_get_queryset()
            if jahrgang_id:
                return base_qs.filter(jahrgang=jahrgang_id)
            return base_qs

        FWmodels.Freiwilliger.objects.get_queryset = get_jahrgang_queryset.__get__(FWmodels.Freiwilliger.objects)

        try:
            return view_func(request, *args, **kwargs)
        finally:
            FWmodels.Freiwilliger.objects.get_queryset = original_get_queryset

    return _wrapped_view

def org_context_processor(request):
    """Context processor to add jahrgaenge to all templates."""
    if hasattr(request, 'user') and request.user.is_authenticated and request.user.role == 'O':
        return {
            'jahrgaenge': FWmodels.Jahrgang.objects.filter(org=request.user.org)
        }
    return {}

allowed_models_to_edit = {
    'einsatzland': FWmodels.Einsatzland,
    'einsatzstelle': FWmodels.Einsatzstelle,
    'freiwilliger': FWmodels.Freiwilliger,
    'aufgabe': FWmodels.Aufgabe,
    'aufgabenprofil': FWmodels.Aufgabenprofil,
    'jahrgang': FWmodels.Jahrgang,
    'kirchenzugehoerigkeit': FWmodels.Kirchenzugehoerigkeit,
    'notfallkontakt': FWmodels.Notfallkontakt,
    'entsendeform': FWmodels.Entsendeform,
    'freiwilligeraufgaben': FWmodels.FreiwilligerAufgaben,
    'referenten': ORGmodels.Referenten,
    'user': Globalmodels.CustomUser
}


# Create your views here.
@login_required
@required_role('O')
@filter_jahrgang
def home(request):
    from Global.views import get_bilder

    # Get latest images
    latest_images = FWmodels.Bilder.objects.filter(
        org=request.user.org
    ).order_by('-date_created')[:6]  # Show last 6 images

    # Get all gallery images and group by bilder
    gallery_images = get_bilder(request)[:6]

    # Get pending tasks
    now = timezone.now().date()
    pending_tasks = FWmodels.FreiwilligerAufgaben.objects.filter(
        org=request.user.org,
        erledigt=False,
        faellig__lte=now + timedelta(days=7)  # Only tasks due within a week or past due
    ).order_by('faellig')  # Order by deadline

    # Add is_overdue flag to tasks
    for task in pending_tasks:
        if task.faellig:
            if task.faellig <= now:
                task.is_overdue = 2  # In past
            else:
                task.is_overdue = 1  # Within one week

    context = {
        'gallery_images': gallery_images,
        'pending_tasks': pending_tasks,
    }
    
    return render(request, 'homeOrg.html', context)


def get_model(model_name):
    if model_name in allowed_models_to_edit:
        return allowed_models_to_edit[model_name]
    return None


@login_required
@required_role('O')
@filter_jahrgang
def save_form(request, form):
    obj = form.save(commit=False)
    obj.org = request.user.org
    obj.save()
    form.save_m2m()


@login_required
@required_role('O')
@filter_jahrgang
def add_object(request, model_name):
    freiwilliger_id = request.GET.get('freiwilliger')
    aufgabe_id = request.GET.get('aufgabe')
    if freiwilliger_id and aufgabe_id:
        freiwilliger = FWmodels.Freiwilliger.objects.get(pk=freiwilliger_id)
        aufgabe = FWmodels.Aufgabe.objects.get(pk=aufgabe_id)

        if not freiwilliger.org == request.user.org or not aufgabe.org == request.user.org:
            return HttpResponse('Nicht erlaubt')

        obj, created = FWmodels.FreiwilligerAufgaben.objects.get_or_create(
            org=request.user.org,
            freiwilliger=freiwilliger,
            aufgabe=aufgabe
        )
        return edit_object(request, model_name, obj.id)
    return edit_object(request, model_name, None)

@login_required
@required_role('O')
@filter_jahrgang
def add_objects_from_excel(request, model_name):
    if request.method == 'POST':
        excel_file = request.FILES['excel_file']
        df = pd.read_excel(excel_file)
        model = get_model(model_name)

        jahrgang_id = request.COOKIES.get('selectedJahrgang')
        if FWmodels.Jahrgang.objects.filter(id=jahrgang_id).exists():
            jahrgang = FWmodels.Jahrgang.objects.get(id=jahrgang_id)
            if jahrgang.org != request.user.org:
                return HttpResponse('Nicht erlaubt')
        else:
            jahrgang = None

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
                if 'jahrgang' in model._meta.fields and jahrgang:
                    obj.jahrgang = jahrgang
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
@filter_jahrgang
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

        if model_name == 'freiwilligeraufgaben':
            return redirect('list_aufgaben_table')
        
        return redirect('list_object_highlight', model_name=model_name, highlight_id=highlight_id)

    return render(request, 'edit_object.html', {'form': form, 'object': model_name})


@login_required
@required_role('O')
@filter_jahrgang
def list_object(request, model_name, highlight_id=None):
    model = get_model(model_name)

    if not model:
        return HttpResponse(f'Kein Model für {model_name} gefunden')

    # Initialize the filter form
    filter_form = ORGforms.FilterForm(model, request.GET, request=request)
    
    # Start with all objects for this organization
    objects = model.objects.filter(org=request.user.org)

    # Apply filters if form is valid
    if filter_form.is_valid():
        # Handle search across all text fields
        search_query = filter_form.cleaned_data.get('search')
        if search_query:
            search_filters = FWmodels.models.Q()
            for field in model._meta.fields:
                if isinstance(field, (FWmodels.models.CharField, FWmodels.models.TextField)):
                    search_filters |= FWmodels.models.Q(**{f'{field.name}__icontains': search_query})
            objects = objects.filter(search_filters)
        
        # Apply specific field filters
        for field in model._meta.fields:
            if field.name in ['org', 'id']:
                continue
                
            if isinstance(field, (FWmodels.models.CharField, FWmodels.models.TextField)):
                value = filter_form.cleaned_data.get(f'filter_{field.name}')
                if value:
                    objects = objects.filter(**{f'{field.name}__icontains': value})
                    
            elif isinstance(field, (FWmodels.models.BooleanField)):
                value = filter_form.cleaned_data.get(f'filter_{field.name}')
                if value:  # Only apply filter if a value is selected
                    objects = objects.filter(**{field.name: value == 'true'})
                    
            elif isinstance(field, FWmodels.models.DateField):
                date_from = filter_form.cleaned_data.get(f'filter_{field.name}_from')
                date_to = filter_form.cleaned_data.get(f'filter_{field.name}_to')
                if date_from:
                    objects = objects.filter(**{f'{field.name}__gte': date_from})
                if date_to:
                    objects = objects.filter(**{f'{field.name}__lte': date_to})
                    
            elif isinstance(field, FWmodels.models.ForeignKey):
                value = filter_form.cleaned_data.get(f'filter_{field.name}')
                if value:
                    objects = objects.filter(**{field.name: value})
    
    # Get both regular fields and many-to-many fields
   
    field_metadata = [
        {'name': field.name, 'verbose_name': field.verbose_name}
        for field in model._meta.fields if field.name != 'org' and field.name != 'id' #and (field.name != 'user' or model._meta.object_name == 'CustomUser')
    ]

    model_fields = [field.name for field in model._meta.fields]

    if model._meta.object_name == 'Aufgabe':
        faellig_art_order = Case(
            When(faellig_art=FWmodels.Aufgabe.FAELLIG_CHOICES[0][0], then=0),  # Weekly tasks first
            When(faellig_art=FWmodels.Aufgabe.FAELLIG_CHOICES[1][0], then=1),  # 'Vorher' tasks second
            When(faellig_art=FWmodels.Aufgabe.FAELLIG_CHOICES[2][0], then=2),  # 'Nachher' tasks third
            default=3
        )
        objects = objects.order_by(faellig_art_order, 'faellig_tag', 'faellig_monat', 'faellig_tage_nach_start', 'faellig_tage_vor_ende')
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
                  'highlight_id': highlight_id})


@login_required
@required_role('O')
@filter_jahrgang
def update_object(request, model_name):
    model = get_model(model_name)

    if not model:
        return JsonResponse({'success': False, 'error': 'Bad Request'}, status=400)

    id = request.POST.get('pk')
    field_name = request.POST.get('field')
    value = request.POST.get('value')

    instance = get_object_or_404(model, id=id)
    if not instance.org == request.user.org:
        return JsonResponse({'success': False, 'error': 'Not allowed'}, status=403)

    if field_name == 'id' or field_name == 'org':
        return JsonResponse({'success': False, 'error': 'Not allowed to edit'}, status=403)

    field = instance._meta.get_field(field_name)

    if isinstance(field, ForeignKey):
        return JsonResponse({'success': False, 'error': 'Not able to edit'}, status=400)

    try:
        # if field type is datetime, convert value to datetime object
        if field.get_internal_type() == 'DateField':
            value = datetime.strptime(value, '%d.%m.%Y')
        if field.get_internal_type() == 'DateTimeField':
            value = datetime.strptime(value, '%d.%m.%Y %H:%M:%S')
        setattr(instance, field_name, value)
        instance.save()
        value = getattr(instance, field_name)
        if field.get_internal_type() == 'DateField':
            value = value.strftime('%d.%m.%Y')
        return JsonResponse({'success': True, 'value': value})

    except Exception as e:
        print(e)
        return JsonResponse({'success': False, 'error': e}, status=400)


@login_required
@required_role('O')
@filter_jahrgang
def delete_object(request, model_name, id):
    model = get_model(model_name)
    if not model:
        return HttpResponse(f'Kein Model für {model_name} gefunden')

    instance = get_object_or_404(model, id=id)
    if not instance.org == request.user.org:
        return HttpResponse('Nicht erlaubt')

    instance.delete()
    return HttpResponseRedirect(f'/org/list/{model_name}/')


@login_required
@required_role('O')
@filter_jahrgang
def list_ampel(request):
    # Get jahrgang filter from cookie
    jahrgang_id = request.COOKIES.get('selectedJahrgang')
    
    # Base queryset for freiwillige
    freiwillige_qs = FWmodels.Freiwilliger.objects.filter(org=request.user.org)
    
    # Apply jahrgang filter if specified
    if jahrgang_id:
        freiwillige_qs = freiwillige_qs.filter(jahrgang=jahrgang_id)
    
    # Order by jahrgang and name
    freiwillige = freiwillige_qs.order_by('-jahrgang', 'last_name', 'first_name')
    
    # Get date range for ampel entries
    date_range = get_ampel_date_range(request.user.org)
    start_date, end_date = date_range['start_date'], date_range['end_date']
    
    # Get ampel entries within date range
    ampel_entries = FWmodels.Ampel.objects.filter(
        freiwilliger__in=freiwillige,
        date__gte=start_date,
        date__lte=end_date
    ).order_by('freiwilliger', 'date')
    
    # Generate month labels
    months = generate_month_labels(start_date, end_date)
    
    # Create and fill ampel matrix
    ampel_matrix = create_ampel_matrix(freiwillige, months, ampel_entries)
    
    # Group freiwillige by jahrgang for template
    grouped_matrix = {}
    for fw in freiwillige:
        if fw.jahrgang not in grouped_matrix:
            grouped_matrix[fw.jahrgang] = {}
        grouped_matrix[fw.jahrgang][fw] = ampel_matrix[fw]
    
    context = {
        'months': months,
        'ampel_matrix': grouped_matrix,
        'current_month': timezone.now().strftime("%b %y"),
        'jahrgang': jahrgang_id
    }
    return render(request, 'list_ampel.html', context=context)

def get_ampel_date_range(org):
    """Helper function to determine the date range for ampel entries."""
    # Get earliest start date
    start_dates = FWmodels.Freiwilliger.objects.filter(org=org).aggregate(
        real_start=Min('start_real'),
        planned_start=Min('start_geplant')
    )
    start_date = start_dates['real_start'] or start_dates['planned_start']

    # Get latest end date
    end_dates = FWmodels.Freiwilliger.objects.filter(org=org).aggregate(
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
@filter_jahrgang
def list_aufgaben(request):

    if request.method == 'POST':
        aufgabe_id = request.POST.get('aufgabe_id')
        aufgabe = FWmodels.FreiwilligerAufgaben.objects.get(pk=aufgabe_id)

        if aufgabe.org == request.user.org:
            aufgabe.erledigt = request.POST.get('erledigt') == 'True'
            aufgabe.pending = request.POST.get('pending') == 'True'
            aufgabe.save()
        return redirect('list_aufgaben')

    # Get jahrgang filter from cookie
    jahrgang_id = request.COOKIES.get('selectedJahrgang')
    
    # Base queryset filters
    base_filter = {'org': request.user.org}
    if jahrgang_id:
        base_filter['freiwilliger__jahrgang'] = jahrgang_id

    # Get filtered tasks for each category
    aufgaben_unfinished = FWmodels.FreiwilligerAufgaben.objects.filter(
        **base_filter,
        erledigt=False,
        pending=False
    )
    
    aufgaben_pending = FWmodels.FreiwilligerAufgaben.objects.filter(
        **base_filter,
        pending=True,
        erledigt=False
    )
    
    aufgaben_finished = FWmodels.FreiwilligerAufgaben.objects.filter(
        **base_filter,
        erledigt=True
    )
    
    from datetime import date
    
    return render(request, 'list_aufgaben.html', context={
        'aufgaben_unfinished': aufgaben_unfinished,
        'aufgaben_pending': aufgaben_pending,
        'aufgaben_finished': aufgaben_finished,
        'today': date.today()
    })

def list_aufgaben_table(request, scroll_to=None):
    if request.method == 'GET' and request.GET.get('fw') and request.GET.get('a'):
        fw_all = request.GET.get('fw') == 'all'
        if fw_all:
            freiwilliger = FWmodels.Freiwilliger.objects.filter(org=request.user.org)
        else:
            freiwilliger = FWmodels.Freiwilliger.objects.filter(pk=request.GET.get('fw'))
        aufgabe = FWmodels.Aufgabe.objects.get(pk=request.GET.get('a'))
        
        for fw in freiwilliger:
            if not fw.org == request.user.org or not aufgabe.org == request.user.org:
                continue

            fw_aufg, created = FWmodels.FreiwilligerAufgaben.objects.get_or_create(
                org=request.user.org,
                freiwilliger=fw,
                aufgabe=aufgabe
            )
        return redirect('list_aufgaben_table_scroll', scroll_to=fw_aufg.id)
    
    if request.method == 'POST':
        aufgabe_id = request.POST.get('aufgabe_id')

        if request.POST.get('reminder') == 'True':
            pass
        else:
            fw_aufg = FWmodels.FreiwilligerAufgaben.objects.get(pk=aufgabe_id)
            if fw_aufg.org == request.user.org:
                fw_aufg.pending = request.POST.get('pending') == 'True'
                fw_aufg.erledigt = request.POST.get('erledigt') == 'True'

                if fw_aufg.erledigt:
                    fw_aufg.erledigt_am = timezone.now()
                else:
                    fw_aufg.erledigt_am = None

                fw_aufg.save()
        return redirect('list_aufgaben_table_scroll', scroll_to=fw_aufg.id)

    freiwillige = FWmodels.Freiwilliger.objects.filter(org=request.user.org).order_by('first_name', 'last_name')
    aufgaben = FWmodels.Aufgabe.objects.filter(org=request.user.org)
    faellig_art_choices = FWmodels.Aufgabe.FAELLIG_CHOICES

    # Order by faellig_art priority (weekly -> vorher -> nachher)
    faellig_art_order = Case(
        When(faellig_art=faellig_art_choices[0][0], then=0),  # Weekly tasks first
        When(faellig_art=faellig_art_choices[1][0], then=1),  # 'Vorher' tasks second
        When(faellig_art=faellig_art_choices[2][0], then=2),  # 'Nachher' tasks third
        default=3
    )
    
    # Apply ordering
    aufgaben = aufgaben.order_by(
        faellig_art_order,
        'faellig_tag',
        'faellig_monat'
    )

    # Get filter type from request or cookie
    filter_type = request.GET.get('f')
    if not filter_type:
        filter_type = request.COOKIES.get('filter_aufgaben_table') or 'None'

    # Apply filter if provided
    if filter_type and filter_type != 'None':
        for choice in faellig_art_choices:
            if choice[0] == filter_type:
                aufgaben = aufgaben.filter(faellig_art=choice[0])
                break

    freiwilliger_aufgaben_matrix = {}
    for freiwilliger in freiwillige:
        freiwilliger_aufgaben_matrix[freiwilliger] = []
        for aufgabe in aufgaben:
            freiwilliger_aufgaben = FWmodels.FreiwilligerAufgaben.objects.filter(freiwilliger=freiwilliger, aufgabe=aufgabe)
            if freiwilliger_aufgaben:
                freiwilliger_aufgaben_matrix[freiwilliger].append(freiwilliger_aufgaben.first())
            else:
                freiwilliger_aufgaben_matrix[freiwilliger].append(aufgabe.id)

    context = {
        'freiwillige': freiwillige,
        'aufgaben': aufgaben,
        'today': date.today(),
        'freiwilliger_aufgaben_matrix': freiwilliger_aufgaben_matrix,
        'faellig_art_choices': faellig_art_choices,
        'filter': filter_type,
        'scroll_to': scroll_to
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
@filter_jahrgang
def aufgaben_assign(request):
    if request.method == 'POST':
        freiwillige = request.POST.getlist('freiwillige')
        profil = request.POST.getlist('profil')
        aufgaben = request.POST.getlist('aufgaben')

        print(freiwillige, profil, aufgaben)

        for f in freiwillige:
            freiwilliger = FWmodels.Freiwilliger.objects.get(pk=f)

            if not freiwilliger.org == request.user.org:
                continue

            for p in profil:
                profil = FWmodels.Aufgabenprofil.objects.get(pk=p)

                if not freiwilliger.org == request.user.org:
                    continue

                FWmodels.FreiwilligerAufgabenprofil.objects.get_or_create(
                    org=request.user.org,
                    aufgabenprofil=profil,
                    freiwilliger=freiwilliger
                )

            for a in aufgaben:
                aufgabe = FWmodels.Aufgabe.objects.get(pk=a)

                if not aufgabe.org == request.user.org or not freiwilliger.org == request.user.org:
                    continue

                FWmodels.FreiwilligerAufgaben.objects.get_or_create(
                    org=request.user.org,
                    aufgabe=aufgabe,
                    freiwilliger=freiwilliger
                )

        return redirect('aufgaben_assign')

    freiwillige = FWmodels.Freiwilliger.objects.filter(org=request.user.org)
    aufgaben = FWmodels.Aufgabe.objects.filter(org=request.user.org)
    profil = FWmodels.Aufgabenprofil.objects.filter(org=request.user.org)

    context = {
        'freiwillige': freiwillige,
        'aufgaben': aufgaben,
        'profil': profil
    }
    return render(request, 'aufgaben_assign.html', context=context)


@login_required
@required_role('O')
@filter_jahrgang
def download_aufgabe(request, id):
    aufgabe = FWmodels.FreiwilligerAufgaben.objects.get(pk=id)
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
@filter_jahrgang
def list_bilder(request):
    bilder = FWmodels.Bilder.objects.filter(org=request.user.org)

    gallery_images = {}

    for bild in bilder:
        gallery_images[bild] = FWmodels.BilderGallery.objects.filter(bilder=bild)

    return render(request, 'list_bilder.html', context={'gallery_images': gallery_images})


@login_required
@required_role('O')
@filter_jahrgang
def download_bild_as_zip(request, id):
    bild = FWmodels.Bilder.objects.get(pk=id)
    if not bild.org == request.user.org:
        return HttpResponse('Nicht erlaubt')
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w') as zipf:
        for i, bild_gallery in enumerate(FWmodels.BilderGallery.objects.filter(bilder=bild)):
            zipf.write(bild_gallery.image.path, f"{bild.user.username}-{bild.titel.replace(' ', '_')}-{bild.date_created.strftime('%Y-%m-%d')}_{i}{os.path.splitext(bild_gallery.image.path)[1]}")
    zip_buffer.seek(0)
    response = HttpResponse(zip_buffer, content_type='application/zip')
    response['Content-Disposition'] = f'attachment; filename="{bild.user.username}_{bild.titel}_{bild.date_created.strftime("%Y-%m-%d")}.zip"'
    return response


@login_required
@required_role('O')
@filter_jahrgang
def dokumente(request):
    return render(request, 'dokumente.html', context={'extends_base': base_template})


@login_required
@required_role('O')
@filter_jahrgang
def statistik(request):
    field_name = request.GET.get('field')
    if field_name:
        if field_name not in [f.name for f in FWmodels.Freiwilliger._meta.fields]:
            return JsonResponse({'error': 'Invalid field'}, status=400)
        
        stats = FWmodels.Freiwilliger.objects.filter(org=request.user.org)\
            .values(field_name)\
            .annotate(count=Count('id'))\
            .order_by(field_name)
        
        # Convert QuerySet to dictionary
        data = {}
        for item in stats:
            value = item[field_name]
            if isinstance(value, int) and any(f.name == field_name and isinstance(f, ForeignKey) for f in FWmodels.Freiwilliger._meta.fields):
                related_obj = FWmodels.Freiwilliger._meta.get_field(field_name).related_model.objects.get(id=value)
                key = str(related_obj)
            else:
                key = str(value) if value is not None else 'Nicht angegeben'
            data[key] = item['count']
        
        return JsonResponse(data)

    freiwillige = FWmodels.Freiwilliger.objects.filter(org=request.user.org)
    filter_for_fields = ['entsendeform', 'einsatzland', 'einsatzstelle', 'kirchenzugehoerigkeit', 'geschlecht', 'ort', 'geburtsdatum']
    if not 'selectedJahrgang' in request.COOKIES:
        filter_for_fields.append('jahrgang')
    all_fields = FWmodels.Freiwilliger._meta.fields
    fields = [field for field in all_fields if field.name in filter_for_fields]
    return render(request, 'statistik.html', context={'freiwillige': freiwillige, 'fields': fields})
