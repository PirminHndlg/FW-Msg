from datetime import datetime

from django.db.models import ForeignKey
from django.shortcuts import render
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404
from django.db.models import Max, F

from FW import models as FWmodels
from FW.views import getOrg
from . import models as ORGmodels
from . import forms as ORGforms

allowed_models_to_edit = {
    'einsatzland': FWmodels.Einsatzland,
    'einsatzstelle': FWmodels.Einsatzstelle,
    'freiwilliger': FWmodels.Freiwilliger,
    'aufgabe': FWmodels.Aufgabe,
    'aufgabenprofil': FWmodels.Aufgabenprofil,
    'jahrgang': FWmodels.Jahrgang,
    'kirchenzugehoerigkeit': FWmodels.Kirchenzugehoerigkeit,
    'notfallkontakt': FWmodels.Notfallkontakt,
    'entsendeform': FWmodels.Entsendeform
}


# Create your views here.
def home(request):
    return render(request, 'homeOrg.html')


def get_model(model_name):
    if model_name in allowed_models_to_edit:
        return allowed_models_to_edit[model_name]
    return None


def save_form(request, form):
    obj = form.save(commit=False)
    obj.org = getOrg(request)
    obj.save()


def add_object(request, model_name):
    return edit_object(request, model_name, None)
    # return render(request, 'add_object.html', {'form': form, 'object': model_name})


def edit_object(request, model_name, id):
    model = get_model(model_name.lower())
    if not model or not model in ORGforms.model_to_form_mapping:
        return HttpResponse(f'Kein Formular für {model_name} gefunden')

    if not id == None:
        instance = get_object_or_404(model, id=id)
        if not instance.org == getOrg(request):
            return HttpResponse('Nicht erlaubt')

        form = ORGforms.model_to_form_mapping[model](request.POST or None, instance=instance)
    else:
        form = ORGforms.model_to_form_mapping[model](request.POST or None)

    if form.is_valid():
        save_form(request, form)
        return HttpResponseRedirect(f'/org/list/{model_name}/')

    return render(request, 'edit_object.html', {'form': form, 'object': model_name})


def list_object(request, model_name):
    model = get_model(model_name)

    if not model:
        return HttpResponse(f'Kein Model für {model_name} gefunden')

    objects = model.objects.filter(org=getOrg(request))
    field_metadata = [
        {'name': field.name, 'verbose_name': field.verbose_name}
        for field in model._meta.fields if field.name != 'org' and field.name != 'id'
    ]
    return render(request, 'list_objects.html',
                  {'objects': objects, 'field_metadata': field_metadata, 'model_name': model_name,
                   'verbose_name': model._meta.verbose_name_plural})


def update_object(request, model_name):
    model = get_model(model_name)

    if not model:
        return JsonResponse({'success': False, 'error': 'Bad Request'}, status=400)

    id = request.POST.get('pk')
    field_name = request.POST.get('field')
    value = request.POST.get('value')

    instance = get_object_or_404(model, id=id)
    if not instance.org == getOrg(request):
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


def delete_object(request, model_name, id):
    model = get_model(model_name)
    if not model:
        return HttpResponse(f'Kein Model für {model_name} gefunden')

    instance = get_object_or_404(model, id=id)
    if not instance.org == getOrg(request):
        return HttpResponse('Nicht erlaubt')

    instance.delete()
    return HttpResponseRedirect(f'/org/list/{model_name}/')


def list_ampel(request):
    org = getOrg(request)
    ampel = [FWmodels.Ampel.objects.filter(freiwilliger=f).order_by('-date').first() for f in
             FWmodels.Freiwilliger.objects.filter(org=org)]

    return render(request, 'list_ampel.html', context={'ampel': ampel})


def list_aufgaben(request):
    org = getOrg(request)
    aufgaben_unfinished = FWmodels.FreiwilligerAufgaben.objects.filter(org=org, erledigt=False, pending=False)
    aufgaben_pending = FWmodels.FreiwilligerAufgaben.objects.filter(org=org, pending=True, erledigt=False)
    aufgaben_finished = FWmodels.FreiwilligerAufgaben.objects.filter(org=org, erledigt=True)
    return render(request, 'list_aufgaben.html', context={
        'aufgaben_unfinished': aufgaben_unfinished,
        'aufgaben_pending': aufgaben_pending,
        'aufgaben_finished': aufgaben_finished
    })
