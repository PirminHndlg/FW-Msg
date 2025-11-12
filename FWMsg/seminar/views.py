from django.shortcuts import redirect, render, get_object_or_404
import json
from datetime import datetime
from django.contrib.auth.decorators import login_required
from django.db.models.functions import Round
from django.http import HttpResponseRedirect, HttpResponse, StreamingHttpResponse
from django.urls import reverse
from django.contrib import messages
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from FWMsg.decorators import required_role
from seminar.models import Einheit, Frage, Fragekategorie, Bewertung, Kommentar, Seminar
from Global.models import Attribute, Einsatzland2 as Einsatzland, Einsatzstelle2 as Einsatzstelle, UserAttribute
from BW.models import Bewerber
from .forms import WishForm, BewerterForm
from django.db.models import Avg, Case, When, IntegerField
from django.contrib.auth.models import User

def required_verschwiegenheit(view_func):
    def wrapper(request, *args, **kwargs):
        seminar = Seminar.objects.get(org=request.user.org)
        if not request.user in seminar.verschwiegenheit_von_user.all():
            return redirect('verschwiegenheit')
        return view_func(request, *args, **kwargs)
    return wrapper

# Create your views here.
def home(request):
    return render(request, 'seminar_index.html')

@login_required
@required_verschwiegenheit
def start(request):
    if request.user.is_authenticated and request.user.role in ['O', 'T', 'E']:
        return redirect('einheit')
    if request.user.is_authenticated and request.user.role == 'B':
        return redirect('land')
    return redirect('login')


@csrf_exempt
@login_required
@required_verschwiegenheit
@required_role('OTE')
def refresh(request):
    response = redirect('seminar_home')
    inserted = []
    edited = []

    for cookie_name in request.COOKIES:
        if cookie_name.startswith('f'):
            data = {}

            data['freiwilliger'] = cookie_name.split('f')[1].split('r')[0]
            data['einheit'] = cookie_name.split('r')[1].split('u')[0]
            data['bewerter'] = cookie_name.split('u')[1]

            if data['bewerter'] != str(request.user.id):
                continue

            cookie = request.COOKIES[cookie_name]

            json_data = json.loads(cookie)

            for key, value in json_data.items():
                data['frage'] = key
                data['antwort'] = value

                insert_response = insert_bewertung(data)

                if insert_response == 1:
                    inserted.append(cookie_name)
                elif insert_response == 2:
                    edited.append(cookie_name)

            response.delete_cookie(cookie_name)

        if cookie_name.startswith('comment'):
            data = {}

            comment = cookie_name.split('comment')[1]
            data['freiwilliger'] = comment.split('r')[0]

            comment = comment.split('r')[1]
            data['einheit'] = comment.split('u')[0]
            comment = comment.split('u')[1]

            if 'c' in comment:
                user = comment.split('c')[0]
            else:
                user = comment.split('n')[0]

            if user != str(request.user.id):
                continue

            data['bewerter'] = user

            if 'c' in comment:
                comment = comment.split('c')[1]
                data['category'] = comment.split('n')[0]

            data['name'] = comment.split('n')[1] == '1'

            cookie = request.COOKIES[cookie_name]
            data['text'] = cookie

            insert_response = insert_comment(request, data)

            if insert_response == 1:
                inserted.append(cookie)
            elif insert_response == 2:
                edited.append(cookie)

            response.delete_cookie(cookie_name)

    messages.success(request,
                     f'Erfolgreich bewertet, {len(inserted)} Bewertungen hinzugefügt, {len(edited)} bearbeitet')

    return response


@required_role('OTE')
@login_required
def verschwiegenheit(request):
    bewerter = request.user

    if request.method == 'POST':
        form = BewerterForm(request.POST, instance=bewerter)
        if not form.is_valid():
            return redirect('start')

        form.save()

        verschwiegenheitsplicht = request.POST.get('verschwiegenheitspflicht')
        if not verschwiegenheitsplicht:
            return redirect('start')
        seminar = Seminar.objects.get(org=bewerter.org)
        seminar.verschwiegenheit_von_user.add(bewerter)
        seminar.save()
        return redirect('einheit')

    form = BewerterForm(instance=bewerter)
    context = {
        'bewerter': bewerter,
        'form': form
    }

    return render(request, 'verschwiegenheitspflicht.html', context=context)


@login_required
@required_verschwiegenheit
@required_role('OTE')
def einheit(request):
    einheiten = Einheit.objects.all()
    user = request.user
    for einheit in einheiten:
        if Bewertung.objects.filter(einheit=einheit, bewerter=user).exists():
            einheit.bewertet = True

    context = {
        'einheiten': einheiten
    }
    return render(request, 'chooseEinheit.html', context)


@login_required
@required_verschwiegenheit
@required_role('OTE')
def choose(request):
    einheit_arg = request.GET.get('einheit')

    # choose only freiwillige that have a seminar
    freiwillige = Bewerber.objects.filter(seminar_bewerber__isnull=False).order_by('user__first_name')
    this_einheit = get_object_or_404(Einheit, pk=einheit_arg)

    context = {
        'freiwillige': freiwillige,
        'einheit': this_einheit
    }

    return render(request, 'chooseBewerber.html', context)


@csrf_exempt
@login_required
@required_verschwiegenheit
@required_role('OTE')
def evaluate(request):
    freiwillige_arg = request.GET.dict()
    einheit_arg = request.GET.get('einheit')
    bewerter = request.user

    fw_ids = []
    fw_bewertet = {}
    for key, value in freiwillige_arg.items():
        if value == 'on' and key.isdigit():
            fw_ids.append(str(key))
            if Bewertung.objects.filter(bewerber_id=key, einheit_id=einheit_arg, bewerter=bewerter).exists():
                bewertungen = Bewertung.objects.filter(bewerber_id=key, einheit_id=einheit_arg, bewerter=bewerter)
                kommentare = Kommentar.objects.filter(bewerber_id=key, einheit_id=einheit_arg, bewerter=bewerter)
                for bewertung in bewertungen:
                    if not key in fw_bewertet:
                        fw_bewertet[key] = {}
                    fw_bewertet[key][bewertung.frage_id] = bewertung.bewertung
                for kommentar in kommentare:
                    if not key in fw_bewertet:
                        fw_bewertet[key] = {}
                    if not 'comment' in fw_bewertet[key]:
                        fw_bewertet[key]['comment'] = {}

                    kategorie = kommentar.kategorie_id
                    if not kategorie:
                        kategorie = 'ohne'

                    if not kategorie in fw_bewertet[key]['comment']:
                        fw_bewertet[key]['comment'][kategorie] = {}

                    fw_bewertet[key]['comment'][kategorie]['text'] = kommentar.text
                    fw_bewertet[key]['comment'][kategorie]['name'] = kommentar.show_name_at_presentation

    frewillige = Bewerber.objects.filter(id__in=fw_ids, seminar_bewerber__isnull=False)
    fragen = Frage.objects.all()
    fragenkategorien = Fragekategorie.objects.all()
    einheit = get_object_or_404(Einheit, pk=einheit_arg)
    user = request.user.id

    context = {
        'freiwillige': frewillige,
        'questions': fragen,
        'categories': fragenkategorien,
        'einheit': einheit,
        'user': user,
        'bewertet': fw_bewertet
    }
    return render(request, 'evaluate.html', context)


def insert_bewertung(data):
    try:
        freiwilliger = Bewerber.objects.get(id=data['freiwilliger'], seminar_bewerber__isnull=False)
        bewerter = User.objects.get(id=data['bewerter'])
        einheit = Einheit.objects.get(id=data['einheit'])
        antwort = data['antwort']
        frage = Frage.objects.get(id=data['frage'])

        bewertung, created = Bewertung.objects.get_or_create(
            org=bewerter.org,
            bewerber=freiwilliger,
            einheit=einheit,
            frage=frage,
            bewerter=bewerter,
            defaults={'bewertung': antwort}
        )

        if not created:
            bewertung.bewertung = data['antwort']
            bewertung.save()
            return 2

        return 1

    except Exception as e:
        messages.error(request, 'Fehler beim Einfügen der Bewertung')
    return 0


def insert_comment(request, data):
    try:
        from django.utils.html import strip_tags
        
        bewerber = Bewerber.objects.get(id=data['freiwilliger'], seminar_bewerber__isnull=False)
        bewerter = User.objects.get(id=data['bewerter'])
        einheit = Einheit.objects.get(id=data['einheit'])
        category = Fragekategorie.objects.get(id=data['category']) if 'category' in data else None
        text = strip_tags(data['text'])
        show_name = data['name']

        defaults = {'show_name_at_presentation': show_name, 'text': text, 'last_modified': datetime.now()}

        comment_data = {
            'org': bewerter.org,
            'bewerber': bewerber,
            'einheit': einheit,
            'bewerter': bewerter,
            'defaults': defaults
        }

        if category:
            comment_data['kategorie'] = category
        else:
            comment_data['kategorie__isnull'] = True

        comment, created = Kommentar.objects.get_or_create(**comment_data)

        if not created:
            comment.text = text
            comment.last_modified = datetime.now()
            comment.save()
            return 2

        return 1
    except Exception as e:
        messages.error(request, 'Fehler beim Einfügen des Kommentars')
        return 0


@csrf_exempt
@login_required
@required_verschwiegenheit
@required_role('OTE')
def evaluate_post(request):
    request_dict = request.POST.dict()
    inserted = []
    edited = []

    response = redirect('seminar_home')

    only = request_dict.get('only')

    for k, v in request_dict.items():
        if 'csrfmiddlewaretoken' in k or 'refresh' in k or 'only' in k:
            continue
        
        k = k.strip()
        v = v.strip()

        data = {}

        if k.startswith('comment'):
            if len(v) < 1:
                continue

            comment = k.split('comment')[1]
            data['freiwilliger'] = comment.split('r')[0]

            if only and only != data['freiwilliger']:
                continue

            comment = comment.split('r')[1]
            data['einheit'] = comment.split('u')[0]
            comment = comment.split('u')[1]

            if 'c' in comment:
                user = comment.split('c')[0]
            else:
                user = comment.split('n')[0]

            if user != str(request.user.id):
                continue

            data['bewerter'] = user

            if 'c' in comment:
                comment = comment.split('c')[1]
                data['category'] = comment.split('n')[0]

            data['name'] = comment.split('n')[1] == '1'

            data['text'] = v

            insert_response = insert_comment(request, data)

            if insert_response == 1:
                inserted.append(k)
            elif insert_response == 2:
                edited.append(k)

            continue

        elif k.startswith('f'):
            buf = k.strip().split('f')[1]
            data['freiwilliger'] = buf.split('q')[0]

            if only and only != data['freiwilliger']:
                continue

            buf = buf.split('q')[1]
            data['frage'] = buf.split('r')[0]
            buf = buf.split('r')[1]
            data['einheit'] = buf.split('u')[0]
            buf = buf.split('u')[1]
            data['bewerter'] = buf

            if data['bewerter'] != str(request.user.id):
                continue

            data['antwort'] = v

            insert_response = insert_bewertung(data)

            if insert_response == 1:
                inserted.append(k)
            elif insert_response == 2:
                edited.append(k)

            cookie_name = f'f{data["freiwilliger"]}q{data["frage"]}r{data["einheit"]}u{data["bewerter"]}'

            if cookie_name in request.COOKIES:
                response.delete_cookie(cookie_name)

    messages.success(request,
                     f'Erfolgreich bewertet, {len(inserted)} Bewertungen hinzugefügt, {len(edited)} bearbeitet')

    return response


@login_required
@required_role('O')
def evaluate_all(request):
    from django.db.models import Q
    
    Kategorien = Fragekategorie.objects.all()

    # Get all Bewerber with their average scores (if they have evaluations)
    # Include those without evaluations as well
    all_bewerber = Bewerber.objects.filter(seminar_bewerber__isnull=False).annotate(
        avg_total=Round(Avg('bewertung__bewertung'), 2)
    ).values(
        'id',
        'user__first_name',
        'user__last_name',
        'endbewertung',
        'avg_total'
    ).order_by(
        # Put those without scores at the end, then order by score
        'avg_total',
        'user__last_name',
        'user__first_name'
    )
    
    # Format the data to match the expected structure
    average_total_per_freiwilliger = [
        {
            'bewerber': b['id'],
            'bewerber__user__first_name': b['user__first_name'],
            'bewerber__user__last_name': b['user__last_name'],
            'bewerber__endbewertung': b['endbewertung'],
            'avg_total': b['avg_total'] or 0
        }
        for b in all_bewerber
    ]
    
    if not all_bewerber.exists() or not average_total_per_freiwilliger:
        msg_text = 'Keine Bewerber:innen vorhanden'
        messages.info(request, msg_text)
        return redirect('seminar_home')

    i = int(request.GET.get('f') or 0)
    if i < 0 or i >= len(average_total_per_freiwilliger):
        i = 0
    freiwilliger_id = average_total_per_freiwilliger[i]['bewerber']
    
    try:
        freiwilliger = Bewerber.objects.prefetch_related('interview_persons').get(id=freiwilliger_id, seminar_bewerber__isnull=False)
    except Bewerber.DoesNotExist:
        msg_text = 'Freiwilliger nicht gefunden'
        messages.info(request, msg_text)
        return redirect('seminar_home')

    fid = int(request.GET.get('fid') or 0)
    if fid:
        freiwilliger_id = fid
        freiwilliger = Bewerber.objects.prefetch_related('interview_persons').get(id=freiwilliger_id, seminar_bewerber__isnull=False)
        for index, item in enumerate(average_total_per_freiwilliger):
            if item['bewerber'] == freiwilliger_id:
                i = index
                break
    
    # Get all attributes for this person_cluster (after final freiwilliger is determined)
    attributes = Attribute.objects.filter(
        visible_in_profile=True, 
        person_cluster=freiwilliger.user.customuser.person_cluster
    ).order_by('name')
    
    # Get existing user attribute values
    existing_user_attributes = {
        ua.attribute_id: ua.value 
        for ua in UserAttribute.objects.filter(user=freiwilliger.user, attribute__in=attributes)
    }
    
    # Combine all attributes with their values (if they exist)
    user_attributes = []
    for attr in attributes:
        user_attributes.append({
            'name': attr.name,
            'value': existing_user_attributes.get(attr.id, None)
        })

    average_bewertung_per_freiwilliger = (
        Bewertung.objects
        .filter(bewerber_id=freiwilliger_id)  # Filter by specific freiwilliger ID
        .values('frage__kategorie')  # Group by 'frage__kategorie'
        .annotate(avg_bewertung=Round(Avg('bewertung'), 2))
    )

    bewertungen_per_freiwilliger = (
        Bewertung.objects
        .filter(bewerber_id=freiwilliger_id)  # Filter by specific freiwilliger ID
        .values('frage__kategorie', 'bewerter', 'einheit')
        .annotate(avg_bewertung=Avg('bewertung'))  # Calculate average for each 'kategorie'
    )

    bewertung_data = {}
    for bewertung in bewertungen_per_freiwilliger:
        if bewertung['frage__kategorie'] not in bewertung_data:
            bewertung_data[bewertung['frage__kategorie']] = []
        bewertung_data[bewertung['frage__kategorie']].append(bewertung['avg_bewertung'])

    kommentare_per_freiwilliger = (
        Kommentar.objects
        .filter(bewerber_id=freiwilliger_id)  # Filter by specific freiwilliger ID
        .filter(show_at_presentation=True)  # Filter by 'show_at_presentation'
        .values('bewerter__first_name', 'bewerter__last_name', 'einheit__name', 'einheit__short_name', 'text',
                'show_name_at_presentation')
    )

    note = average_total_per_freiwilliger[i]['avg_total']
    if note and (not freiwilliger.note or freiwilliger.note != note):
        freiwilliger.note = note
        freiwilliger.save()

    context = {
        'kommentare': kommentare_per_freiwilliger,
        'result': average_bewertung_per_freiwilliger,
        'bewertungen': bewertung_data,
        'all_results': average_total_per_freiwilliger,
        'freiwilliger': freiwilliger,
        'user_attributes': user_attributes,
        'kategorien': Kategorien,
        'avg': average_total_per_freiwilliger[i],
        'back': i - 1 if i > 0 else -1,
        'next': i + 1 if i < len(average_total_per_freiwilliger) - 1 else -1,
        'kirchenzugehoerigkeit_with_img': ['Evangelisch', 'Katholisch', 'EKBO', 'Anhalt']
    }

    return render(request, 'powerPoint.html', context)


@login_required
@required_role('O')
def summerizeComments(request):
    all = request.GET.get('all')

    kommentare_per_freiwilliger = (
        Kommentar.objects
        .filter(show_at_presentation=True)  # Filter by 'show_at_presentation'
        .values('freiwilliger', 'text')
    )

    if all:
        freiwillige = Bewerber.objects.filter(seminar_bewerber__isnull=False)
    else:
        freiwillige = Bewerber.objects.filter(kommentar_zusammenfassung='', seminar_bewerber__isnull=False)

    alle_kommentare = {}

    def generate():
        for freiwilliger in freiwillige:
            freiwilliger_kommentartext = ''
            for kommentar in kommentare_per_freiwilliger:
                if kommentar['freiwilliger'] == freiwilliger.id and kommentar['text'] != '':
                    freiwilliger_kommentartext += kommentar['text'] + '\n\n'
            alle_kommentare[freiwilliger.id] = {'name': f'{freiwilliger.first_name} {freiwilliger.last_name}',
                                                'text': freiwilliger_kommentartext}

            if freiwilliger_kommentartext != '':
                prompt = (
                    f"Fasse die folgenden Kommentare über {freiwilliger.first_name} in wenigen kurzen Wörtern oder Phrasen zusammen: "
                    f"'{freiwilliger_kommentartext}'."
                    "Die Antwort sollte nur Stichwörter oder Begriffe enthalten, keine ganzen Sätze."
                )
                response_text = get_chat_response(prompt)
                alle_kommentare[freiwilliger.id]['summary'] = response_text

                freiwilliger.kommentar_zusammenfassung = response_text
                freiwilliger.save()

                yield f'{freiwilliger.first_name}: "{response_text}"\n\n'

        # generate()
        yield f'<br><hr><br>'
        yield '<a href="{% url "start" %}">Zurück zur Startseite</a><br>'

    # return HttpResponse(json.dumps(alle_kommentare, indent=4))

    return StreamingHttpResponse(generate(), content_type="text/plain; charset=utf-8")


@login_required
@required_role('O')
def insert_geeingnet(request):
    data = request.GET.dict()

    f = data['f']
    g = data['g']

    if g not in dict(Bewerber.bewertungsmoeglicheiten).keys() and g != 'None':
        return HttpResponse('Invalid value', status=400)

    freiwilliger = Bewerber.objects.get(id=f, seminar_bewerber__isnull=False)
    freiwilliger.endbewertung = g
    freiwilliger.save()

    return HttpResponse('Success', status=200)


@login_required
@required_role('O')
def assign(request, scroll_to=None):
    stelle = request.GET.get('land')
    freiwilliger = request.GET.get('fw')

    if stelle and freiwilliger:
        try:
            freiwilliger_obj = Bewerber.objects.get(id=freiwilliger, org=request.user.org, seminar_bewerber__isnull=False)
            if stelle == 'None':
                freiwilliger_obj.zuteilung = None
            else:
                stelle_obj = Einsatzstelle.objects.get(id=stelle, org=request.user.org)
                freiwilliger_obj.zuteilung = stelle_obj
            
            freiwilliger_obj.save()
        except (Bewerber.DoesNotExist, Einsatzstelle.DoesNotExist):
            messages.error(request, 'Fehler bei der Zuteilung. Bitte versuchen Sie es erneut.')
        
        if stelle and stelle != 'None':
            return redirect('assign_scroll', scroll_to=stelle)
        else:
            return redirect('assign')

    # Get all volunteers for the current organization
    freiwillige = (
        Bewerber.objects
        .filter(org=request.user.org, seminar_bewerber__isnull=False)
        .filter(seminar_bewerber__isnull=False)
        .select_related('user', 'zuteilung', 'first_wish_einsatzstelle', 'first_wish_einsatzland',
                       'second_wish_einsatzstelle', 'second_wish_einsatzland',
                       'third_wish_einsatzstelle', 'third_wish_einsatzland',
                       'no_wish_einsatzstelle', 'no_wish_einsatzland')
        .annotate(
            custom_order=Case(
                When(endbewertung__startswith='G', then=0),
                When(endbewertung__startswith='B', then=1),
                When(endbewertung__startswith='N', then=2),
                default=3,
                output_field=IntegerField(),
            )
        )
        .order_by('custom_order', 'note')
        .distinct()
    )

    freiwillige_ohne_zuteilung = freiwillige.filter(zuteilung=None)
    freiwillige_mit_zuteilung = freiwillige.exclude(zuteilung=None)

    # Get countries for the current organization
    laender = Einsatzland.objects.filter(org=request.user.org).order_by('name')
    
    laender_arg = []

    for land in laender:
        land_dict = {}
        land_dict['land'] = land
        einsatzstellen = Einsatzstelle.objects.filter(land=land, org=request.user.org).order_by('name')
        land_dict['stellen'] = []
        for stelle in einsatzstellen:
            freiwillige_land = (
                freiwillige_mit_zuteilung
                .filter(zuteilung=stelle)
                .annotate(
                    custom_order=Case(
                        When(endbewertung__startswith='G', then=0),
                        When(endbewertung__startswith='B', then=1),
                        default=2,
                        output_field=IntegerField(),
                    )
                )
                .order_by('custom_order', 'note')
            )
            land_dict['stellen'].append((stelle, freiwillige_land))
        laender_arg.append(land_dict)

    context = {
        'freiwillige': freiwillige,
        'freiwillige_ohne_zuteilung': freiwillige_ohne_zuteilung,
        'freiwillige_mit_zuteilung': freiwillige_mit_zuteilung,
        'laender': laender_arg,
        'scroll_to': scroll_to
    }

    return render(request, 'assign.html', context=context)


@login_required
@required_role('O')
def auto_assign(request):
    org = request.user.org
    
    freiwillige_geeignet = Bewerber.objects.filter(
        org=org, endbewertung__startswith='G', zuteilung=None, seminar_bewerber__isnull=False
    ).order_by('note')
    freiwillige_bedingt_geeignet = Bewerber.objects.filter(
        org=org, endbewertung__startswith='B', zuteilung=None, seminar_bewerber__isnull=False
    ).order_by('note')

    all_freiwille = list(freiwillige_geeignet) + list(freiwillige_bedingt_geeignet)
    
    assigned_count = 0

    for freiwilliger in all_freiwille:
        def stelle_verfuegbar(stelle):
            if not stelle or stelle.max_freiwillige is None:
                return False
            freiwilliger_with_stelle = Bewerber.objects.filter(zuteilung=stelle, org=org, seminar_bewerber__isnull=False)
            return freiwilliger_with_stelle.count() < stelle.max_freiwillige

        first_wish = freiwilliger.first_wish_einsatzstelle
        second_wish = freiwilliger.second_wish_einsatzstelle
        third_wish = freiwilliger.third_wish_einsatzstelle

        wish_list = [first_wish, second_wish, third_wish]

        for wish in wish_list:
            if wish and stelle_verfuegbar(wish):
                freiwilliger.zuteilung = wish
                freiwilliger.save()
                assigned_count += 1
                break

    if assigned_count > 0:
        messages.success(request, f'Automatische Zuteilung abgeschlossen. {assigned_count} Freiwillige wurden zugeteilt.')
    else:
        messages.info(request, 'Keine automatischen Zuweisungen möglich. Alle Wünsche sind bereits belegt oder nicht verfügbar.')

    return redirect('assign')


@login_required
@required_role('O')
def seminar_settings(request):
    from .forms import SeminarForm, EinheitForm, FragekategorieForm, FrageForm
    from .models import Seminar, Einheit, Fragekategorie, Frage
    
    # Get current user's org
    org = request.user.org
    
    # Handle form submissions
    if request.method == 'POST':
        form_type = request.POST.get('form_type')
        
        if form_type == 'seminar':
            if 'seminar_id' in request.POST and request.POST['seminar_id'] != '':
                seminar = get_object_or_404(Seminar, id=request.POST['seminar_id'], org=org)
                form = SeminarForm(request.POST, instance=seminar)
            else:
                form = SeminarForm(request.POST)
            
            if form.is_valid():
                seminar = form.save(commit=False)
                seminar.org = org
                seminar.save()
                messages.success(request, 'Seminar erfolgreich gespeichert!')
                return HttpResponseRedirect(reverse('seminar_settings') + '#seminar')
                
        elif form_type == 'einheit':
            if 'einheit_id' in request.POST and request.POST['einheit_id'] != '':
                einheit = get_object_or_404(Einheit, id=request.POST['einheit_id'], org=org)
                form = EinheitForm(request.POST, instance=einheit)
            else:
                form = EinheitForm(request.POST)
            
            if form.is_valid():
                einheit = form.save(commit=False)
                einheit.org = org
                einheit.save()
                messages.success(request, 'Einheit erfolgreich gespeichert!')
                return HttpResponseRedirect(reverse('seminar_settings') + '#einheit')
                
        elif form_type == 'fragekategorie':
            if 'kategorie_id' in request.POST and request.POST['kategorie_id'] != '':
                kategorie = get_object_or_404(Fragekategorie, id=request.POST['kategorie_id'], org=org)
                form = FragekategorieForm(request.POST, instance=kategorie)
            else:
                form = FragekategorieForm(request.POST)
            
            if form.is_valid():
                kategorie = form.save(commit=False)
                kategorie.org = org
                kategorie.save()
                messages.success(request, 'Fragekategorie erfolgreich gespeichert!')
                return HttpResponseRedirect(reverse('seminar_settings') + '#kategorie')
                
        elif form_type == 'frage':
            if 'frage_id' in request.POST and request.POST['frage_id'] != '':
                frage = get_object_or_404(Frage, id=request.POST['frage_id'], org=org)
                form = FrageForm(request.POST, instance=frage, org=org)
            else:
                form = FrageForm(request.POST, org=org)
            
            if form.is_valid():
                frage = form.save(commit=False)
                frage.org = org
                frage.save()
                messages.success(request, 'Frage erfolgreich gespeichert!')
                return HttpResponseRedirect(reverse('seminar_settings') + '#frage')
    
    # Handle deletions
    if request.method == 'GET' and 'delete' in request.GET:
        delete_type = request.GET.get('delete')
        delete_id = request.GET.get('id')
        
        if delete_type == 'seminar':
            seminar = get_object_or_404(Seminar, id=delete_id, org=org)
            seminar.delete()
            messages.success(request, 'Seminar erfolgreich gelöscht!')
            return HttpResponseRedirect(reverse('seminar_settings') + '#seminar')
        elif delete_type == 'einheit':
            einheit = get_object_or_404(Einheit, id=delete_id, org=org)
            einheit.delete()
            messages.success(request, 'Einheit erfolgreich gelöscht!')
            return HttpResponseRedirect(reverse('seminar_settings') + '#einheit')
        elif delete_type == 'fragekategorie':
            kategorie = get_object_or_404(Fragekategorie, id=delete_id, org=org)
            kategorie.delete()
            messages.success(request, 'Fragekategorie erfolgreich gelöscht!')
            return HttpResponseRedirect(reverse('seminar_settings') + '#kategorie')
        elif delete_type == 'frage':
            frage = get_object_or_404(Frage, id=delete_id, org=org)
            frage.delete()
            messages.success(request, 'Frage erfolgreich gelöscht!')
            return HttpResponseRedirect(reverse('seminar_settings') + '#frage')
        
        return redirect('seminar_settings')
    
    # Get all objects for the current org
    seminare = Seminar.objects.filter(org=org)
    einheiten = Einheit.objects.filter(org=org)
    fragekategorien = Fragekategorie.objects.filter(org=org)
    fragen = Frage.objects.filter(org=org)
    
    # Initialize forms
    seminar_form = SeminarForm()
    einheit_form = EinheitForm()
    fragekategorie_form = FragekategorieForm()
    frage_form = FrageForm(org=org)
    
    context = {
        'seminare': seminare,
        'einheiten': einheiten,
        'fragekategorien': fragekategorien,
        'fragen': fragen,
        'seminar_form': seminar_form,
        'einheit_form': einheit_form,
        'fragekategorie_form': fragekategorie_form,
        'frage_form': frage_form,
    }
    
    return render(request, 'seminar_settings.html', context)



@login_required
@required_role('B')
def seminar_land(request):
    seminar = Seminar.objects.filter(org=request.user.org).first()
    
    if timezone.now() < seminar.get_deadline_start():
        message_text = 'Die Frist für die Auswahl des Einsatzlandes ist noch nicht begonnen.'
        messages.info(request, message_text)
        return redirect('seminar_home')

    if timezone.now() > seminar.get_deadline_end():
        message_text = 'Die Frist für die Auswahl des Einsatzlandes ist abgelaufen.'
        messages.info(request, message_text)
        return redirect('seminar_home')

    if request.method == 'POST':
        try:
            freiwilliger_instance = Bewerber.objects.get(user=request.user, seminar_bewerber__isnull=False)
        except Bewerber.DoesNotExist:
            # Handle the case where the user does not have a Bewerber instance
            return HttpResponse('User not found', status=404)

        form = WishForm(request.POST, instance=freiwilliger_instance)
        if form.is_valid():
            # Process the data in form.cleaned_data
            form.save()

            # Get sanitized values from cleaned_data for safe message display
            first = form.cleaned_data.get('first_wish', '')
            second = form.cleaned_data.get('second_wish', '')
            third = form.cleaned_data.get('third_wish', '')
            no_wish = form.cleaned_data.get('no_wish', '')
            
            messages.success(request, 
                f'Deine Auswahl wurde gespeichert: <br>1) {first or "-"} <br>2) {second or "-"}<br>3) {third or "-"}<br>nicht) {no_wish or "-"}')

            # Redirect to a new URL or render a success message
            return redirect('seminar_home')
    else:
        freiwilliger_exists = Bewerber.objects.filter(user=request.user, seminar_bewerber__isnull=False).exists()
        if not freiwilliger_exists:
            msg_text = 'Du bist kein Bewerber/keine Bewerberin, der für das Seminar eingeladen wurde. Bitte einen anderen Login nutzen'
            messages.info(request, msg_text)
            return redirect('start')
        form = WishForm(instance=Bewerber.objects.get(user=request.user, seminar_bewerber__isnull=False))
        deadline_hour_left = int((seminar.get_deadline_end() - timezone.now()).total_seconds() // 3600)
    return render(request, 'seminar_land.html', {'form': form, 'deadline_hour_left': deadline_hour_left})
