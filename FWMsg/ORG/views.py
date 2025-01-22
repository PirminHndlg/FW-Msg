from datetime import datetime, timedelta
import io
import os
import zipfile

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

from FW import models as FWmodels
from . import models as ORGmodels
from . import forms as ORGforms

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

def org_required(view_func):
    """Decorator to check if user has an associated organization and apply jahrgang filter."""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(settings.LOGIN_URL)
        if request.user.role != 'O':
            messages.error(request, 'Kein Zugriff - Sie sind keine Organisation')
            print(request.user.role)
            return redirect(settings.LOGIN_URL)

        # Get jahrgang from cookie
        jahrgang_id = request.COOKIES.get('selectedJahrgang')

        # Store original queryset method
        original_get_queryset = FWmodels.Freiwilliger.objects.get_queryset

        # Define new queryset method
        def get_filtered_queryset(manager):
            base_qs = original_get_queryset()
            if jahrgang_id:
                return base_qs.filter(jahrgang=jahrgang_id)
            return base_qs

        # Apply the patch
        FWmodels.Freiwilliger.objects.get_queryset = get_filtered_queryset.__get__(FWmodels.Freiwilliger.objects)
        
        try:
            return view_func(request, *args, **kwargs)
        finally:
            # Restore original method
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
    'freiwilligeraufgaben': FWmodels.FreiwilligerAufgaben
}


# Create your views here.
@org_required
@login_required
def home(request):
    # Get latest images
    latest_images = FWmodels.Bilder.objects.filter(
        org=request.user.org
    )[:6]  # Show last 6 images

    # Get all gallery images and group by bilder
    gallery_images = {}
    for gallery_image in FWmodels.BilderGallery.objects.filter(bilder__in=latest_images):
        if gallery_image.bilder not in gallery_images:
            gallery_images[gallery_image.bilder] = []
        gallery_images[gallery_image.bilder].append(gallery_image)

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


@org_required
@login_required
def save_form(request, form):
    obj = form.save(commit=False)
    obj.org = request.user.org
    obj.save()
    form.save_m2m()


@org_required
@login_required
def add_object(request, model_name):
    return edit_object(request, model_name, None)
    # return render(request, 'add_object.html', {'form': form, 'object': model_name})


@org_required
@login_required
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
            instance=instance
        )
    else:
        form = ORGforms.model_to_form_mapping[model](
            request.POST or None,
            request.FILES or None
        )

    if form.is_valid():
        save_form(request, form)
        return HttpResponseRedirect(f'/org/list/{model_name}/')

    return render(request, 'edit_object.html', {'form': form, 'object': model_name})


@org_required
@login_required
def list_object(request, model_name):
    model = get_model(model_name)

    if not model:
        return HttpResponse(f'Kein Model für {model_name} gefunden')

    # Initialize the filter form
    filter_form = ORGforms.FilterForm(model, request.GET or None)
    
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
        for field in model._meta.fields if field.name != 'org' and field.name != 'id'
    ]
    
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
                  'filter_form': filter_form})


@org_required
@login_required
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


@org_required
@login_required
def delete_object(request, model_name, id):
    model = get_model(model_name)
    if not model:
        return HttpResponse(f'Kein Model für {model_name} gefunden')

    instance = get_object_or_404(model, id=id)
    if not instance.org == request.user.org:
        return HttpResponse('Nicht erlaubt')

    instance.delete()
    return HttpResponseRedirect(f'/org/list/{model_name}/')


@org_required
@login_required
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
    ).order_by('freiwilliger', '-date')
    
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

@org_required
@login_required
def list_ampel_history(request, fid):
    freiwilliger = get_object_or_404(FWmodels.Freiwilliger, pk=fid)
    if not freiwilliger.org == request.user.org:
        return HttpResponse('Nicht erlaubt')
    ampel = FWmodels.Ampel.objects.filter(freiwilliger=freiwilliger).order_by('-date')
    return render(request, 'list_ampel_history.html', context={'ampel': ampel, 'freiwilliger': freiwilliger})


@org_required
@login_required
def list_aufgaben(request):
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
    
    return render(request, 'list_aufgaben.html', context={
        'aufgaben_unfinished': aufgaben_unfinished,
        'aufgaben_pending': aufgaben_pending,
        'aufgaben_finished': aufgaben_finished
    })


@org_required
@login_required
def aufgaben_assign(request, jahrgang=None):
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

    if jahrgang:
        # check if jahrgang is existing and belongs to org
        jahrgang_exists = FWmodels.Jahrgang.objects.filter(pk=jahrgang).exists()
        if jahrgang_exists:
            jahrgang = FWmodels.Jahrgang.objects.get(pk=jahrgang)
            if not jahrgang.org == request.user.org:
                return HttpResponse('Nicht erlaubt')
            freiwillige = FWmodels.Freiwilliger.objects.filter(jahrgang=jahrgang)
        else:
            freiwillige = FWmodels.Freiwilliger.objects.filter(org=request.user.org)
    else:
        freiwillige = FWmodels.Freiwilliger.objects.filter(org=request.user.org)

    jahrgaenge = FWmodels.Jahrgang.objects.filter(org=request.user.org)
    aufgaben = FWmodels.Aufgabe.objects.filter(org=request.user.org)
    profil = FWmodels.Aufgabenprofil.objects.filter(org=request.user.org)

    context = {
        'jahr': jahrgang,
        'jahrgaenge': jahrgaenge,
        'freiwillige': freiwillige,
        'aufgaben': aufgaben,
        'profil': profil
    }
    return render(request, 'aufgaben_assign.html', context=context)


@org_required
@login_required
def list_bilder(request):
    bilder = FWmodels.Bilder.objects.filter(org=request.user.org)

    gallery_images = {}

    for bild in bilder:
        gallery_images[bild] = FWmodels.BilderGallery.objects.filter(bilder=bild)

    return render(request, 'list_bilder.html', context={'gallery_images': gallery_images})


@org_required
@login_required
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


@org_required
@login_required
def dokumente(request):
    return render(request, 'dokumente.html', context={'extends_base': base_template})
