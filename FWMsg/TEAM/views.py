from django.utils import timezone
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from Global.models import Freiwilliger, Referenten, Einsatzstelle, Ampel

from ORG.views import filter_person_cluster, _get_ampel_matrix
from FWMsg.decorators import required_role
base_template = 'baseTeam.html'

# Create your views here.
@login_required
@required_role('T')
def home(request):
    return render(request, 'teamHome.html')

def _get_Freiwillige(request):
    team_exists = Referenten.objects.filter(user=request.user).exists()
    if team_exists:
        team = Referenten.objects.get(user=request.user)
        countries = team.land.all()
        return Freiwilliger.objects.filter(einsatzland__in=countries)
    else:
        return []

@filter_person_cluster
@login_required
@required_role('T')
def contacts(request):
    freiwillige = _get_Freiwillige(request)

    fw_cards = []
    for fw in freiwillige:
        fw_cards.append({
            'title': fw.first_name + ' ' + fw.last_name,
            'items': [
                {'icon': 'envelope', 'value': fw.email, 'type': 'email'},
                {'icon': 'phone', 'value': fw.phone, 'type': 'phone'}
            ]
        })

    return render(request, 'teamContacts.html', {'freiwillige': freiwillige, 'fw_cards': fw_cards})


@filter_person_cluster
@login_required
@required_role('T')
def ampelmeldung(request):
    from Global.views import check_organization_context

    freiwillige = _get_Freiwillige(request)
    ampel_matrix, months = _get_ampel_matrix(request, freiwillige)

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
    team_exists = Referenten.objects.filter(user=request.user).exists()
    if team_exists:
        team = Referenten.objects.get(user=request.user)
        einsatzstellen = Einsatzstelle.objects.filter(land__in=team.land.all())
        return render(request, 'teamEinsatzstellen.html', {'einsatzstellen': einsatzstellen})
    else:
        msg = 'Bitte wählen Sie ein Einsatzland'
        return render(request, 'teamEinsatzstellen.html', {'msg': msg})

@filter_person_cluster
@login_required
@required_role('T')
def laender(request):
    team_exists = Referenten.objects.filter(user=request.user).exists()
    if team_exists:
        team = Referenten.objects.get(user=request.user)
        laender = team.land.all()
        return render(request, 'teamLaender.html', {'laender': laender})
    else:
        msg = 'Bitte wählen Sie ein Einsatzland'
        return render(request, 'teamLaender.html', {'msg': msg})
