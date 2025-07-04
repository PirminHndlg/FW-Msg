from django.shortcuts import redirect, render, get_object_or_404
import json
from datetime import datetime
from django.contrib.auth.decorators import login_required
from django.db.models.functions import Round
from django.http import HttpResponseRedirect, HttpResponse, StreamingHttpResponse
from django.contrib import messages
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from FWMsg.decorators import required_role
from seminar.models import Einheit, Frage, Fragekategorie, Bewertung, Kommentar, DeadlineDateTime
from Global.models import Einsatzland2 as Einsatzland, Einsatzstelle2 as Einsatzstelle
from BW.models import Bewerber
from .forms import WishForm, BewerterForm
from django.db.models import Avg, Case, When, IntegerField
from django.contrib.auth.models import User


# Create your views here.
def home(request):
    return render(request, 'seminar_index.html')


@login_required
def start(request):
    print(request.user.role)
    if request.user.is_authenticated and request.user.role in ['O', 'T', 'E']:
        # return HttpResponseRedirect('/verschwiegenheit')
        return redirect('einheit')
    if request.user.is_authenticated and request.user.role == 'B':
        return redirect('land')
    return redirect('login')


@csrf_exempt
@required_role('OTE')
def refresh(request):
    response = HttpResponseRedirect('/')
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
            print(f'Deleted cookie: {cookie_name}')

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

            insert_response = insert_comment(data)

            if insert_response == 1:
                inserted.append(cookie)
            elif insert_response == 2:
                edited.append(cookie)

            response.delete_cookie(cookie_name)
            print(f'Deleted cookie: {cookie_name}')

    messages.success(request,
                     f'Erfolgreich bewertet, {len(inserted)} Bewertungen hinzugefügt, {len(edited)} bearbeitet')

    return response


@required_role('OTE')
def verschwiegenheit(request):
    bewerter = Bewerter.objects.get(user=request.user)

    if request.method == 'POST':
        form = BewerterForm(request.POST, instance=bewerter)
        if not form.is_valid():
            return redirect('start')

        form.save()

        verschwiegenheitsplicht = request.POST.get('verschwiegenheitspflicht')
        if not verschwiegenheitsplicht:
            return redirect('start')
        bewerter = Bewerter.objects.get(user=request.user)
        bewerter.verschwiegenheit = True
        bewerter.verschwiegenheit_datetime = datetime.now()
        bewerter.save()
        return redirect('einheit')

    form = BewerterForm(instance=bewerter)
    if bewerter.geburtsdatum:
        form.fields['geburtsdatum'].widget.attrs['value'] = bewerter.geburtsdatum.strftime('%Y-%m-%d')
    if bewerter.rolle == 'E':
        form.fields['geburtsdatum'].label = 'Geburtsdatum'
        form.fields['geburtsdatum'].widget.attrs['required'] = 'True'

    context = {
        'bewerter': bewerter,
        'form': form
    }

    return render(request, 'verschwiegenheitspflicht.html', context=context)


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


@required_role('OTE')
def choose(request):
    einheit_arg = request.GET.get('einheit')

    freiwillige = Bewerber.objects.all().order_by('user__first_name')
    this_einheit = get_object_or_404(Einheit, pk=einheit_arg)

    context = {
        'freiwillige': freiwillige,
        'einheit': this_einheit
    }

    return render(request, 'chooseBewerber.html', context)


@csrf_exempt
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
            print(f'key: {key}')
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

    print(fw_bewertet)

    frewillige = Bewerber.objects.filter(id__in=fw_ids)
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
    # print(data)
    try:
        freiwilliger = Bewerber.objects.get(id=data['freiwilliger'])
        bewerter = User.objects.get(id=data['bewerter'])
        einheit = Einheit.objects.get(id=data['einheit'])
        antwort = data['antwort']
        frage = Frage.objects.get(id=data['frage'])

        bewertung, created = Bewertung.objects.get_or_create(
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
        print('Error while inserting Bewertung')
        print(e)
    return 0


def insert_comment(data):
    # print(data)
    try:
        freiwilliger = Bewerber.objects.get(id=data['freiwilliger'])
        bewerter = Bewerter.objects.get(user_id=data['bewerter'])
        einheit = Einheit.objects.get(id=data['einheit'])
        category = Fragekategorie.objects.get(id=data['category']) if 'category' in data else None
        text = data['text']
        show_name = data['name']

        defaults = {'show_name_at_presentation': show_name, 'text': text, 'last_modified': datetime.now()}

        comment_data = {
            'freiwilliger': freiwilliger,
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
        print('Error while inserting Kommentar')
        print(e)
        return 0


@csrf_exempt
@required_role('OTE')
def evaluate_post(request):
    request_dict = request.POST.dict()
    # print(request_dict)
    inserted = []
    edited = []

    response = redirect('home-seminar')

    only = request_dict.get('only')

    for k, v in request_dict.items():
        if 'csrfmiddlewaretoken' in k or 'refresh' in k or 'only' in k:
            continue
        
        print(k, v)

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

            insert_response = insert_comment(data)

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
                print(f'Deleted cookie: {cookie_name}')

    messages.success(request,
                     f'Erfolgreich bewertet, {len(inserted)} Bewertungen hinzugefügt, {len(edited)} bearbeitet')

    return response


@required_role('O')
def evaluate_all(request):
    Kategorien = Fragekategorie.objects.all()

    average_total_per_freiwilliger = (
        Bewertung.objects
        .values('bewerber', 'bewerber__user__first_name', 'bewerber__user__last_name',
                'bewerber__endbewertung')  # Group by 'freiwilliger'
        .annotate(avg_total=Round(Avg('bewertung'), 2))  # Calculate total average 'bewertung'
        .order_by('avg_total')
    )

    if not average_total_per_freiwilliger:
        msg_text = 'Noch keine Bewertungen vorhanden'
        messages.info(request, msg_text)
        return redirect('start')

    i = int(request.GET.get('f') or 0)
    if i < 0 or i >= len(average_total_per_freiwilliger):
        i = 0
    freiwilliger_id = average_total_per_freiwilliger[i]['bewerber']
    freiwilliger = Bewerber.objects.get(id=freiwilliger_id)

    fid = int(request.GET.get('fid') or 0)
    print(fid)
    if fid:
        freiwilliger_id = fid
        freiwilliger = Bewerber.objects.get(id=freiwilliger_id)
        for index, item in enumerate(average_total_per_freiwilliger):
            if item['freiwilliger'] == freiwilliger_id:
                i = index
                break

    print(freiwilliger_id, i)

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
    if not freiwilliger.note or freiwilliger.note != note:
        freiwilliger.note = note
        freiwilliger.save()

    context = {
        'kommentare': kommentare_per_freiwilliger,
        'result': average_bewertung_per_freiwilliger,
        'bewertungen': bewertung_data,
        'all_results': average_total_per_freiwilliger,
        'freiwilliger': freiwilliger,
        'kategorien': Kategorien,
        'avg': average_total_per_freiwilliger[i],
        'back': i - 1 if i > 0 else -1,
        'next': i + 1 if i < len(average_total_per_freiwilliger) - 1 else -1,
        'kirchenzugehoerigkeit_with_img': ['Evangelisch', 'Katholisch', 'EKBO', 'Anhalt']
    }

    return render(request, 'powerPoint.html', context)


@required_role('O')
def summerizeComments(request):
    all = request.GET.get('all')

    kommentare_per_freiwilliger = (
        Kommentar.objects
        .filter(show_at_presentation=True)  # Filter by 'show_at_presentation'
        .values('freiwilliger', 'text')
    )

    if all:
        freiwillige = Bewerber.objects.all()
    else:
        freiwillige = Bewerber.objects.filter(kommentar_zusammenfassung='')

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


@required_role('O')
def insert_geeingnet(request):
    data = request.GET.dict()
    print(data)

    f = data['f']
    g = data['g']

    print(Bewerber.bewertungsmoeglicheiten)

    if g not in dict(Bewerber.bewertungsmoeglicheiten).keys() and g != 'None':
        return HttpResponse('Invalid value', status=400)

    freiwilliger = Bewerber.objects.get(id=f)
    freiwilliger.endbewertung = g
    freiwilliger.save()

    print(freiwilliger.endbewertung)

    return HttpResponse('Success', status=200)


@required_role('O')
def assign(request):
    stelle = request.GET.get('land')
    freiwilliger = request.GET.get('fw')

    if stelle and freiwilliger:
        freiwilliger = Bewerber.objects.get(id=freiwilliger)
        if stelle == 'None':
            freiwilliger.zuteilung = None
        else:
            stelle = Einsatzstelle.objects.get(id=stelle)
            freiwilliger.zuteilung = stelle
        freiwilliger.save()

    freiwillige = (
        Bewerber.objects
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
    )

    freiwillige_ohne_zuteilung = freiwillige.filter(zuteilung=None)
    freiwillige_mit_zuteilung = freiwillige.exclude(zuteilung=None)

    laender = Einsatzland.objects.filter().order_by('name')
    # laender = Einsatzland.objects.all()

    laender_arg = []

    for land in laender:
        land_dict = {}
        land_dict['land'] = land
        einsatzstellen = Einsatzstelle.objects.filter(land=land)
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
        'laender': laender_arg
    }

    return render(request, 'assign.html', context=context)


@required_role('O')
def auto_assign(request):
    freiwillige_geeignet = Bewerber.objects.filter(endbewertung__startswith='G', zuteilung=None).order_by('note')
    freiwillige_bedingt_geeignet = Bewerber.objects.filter(endbewertung__startswith='B', zuteilung=None).order_by(
        'note')

    all_freiwille = list(freiwillige_geeignet) + list(freiwillige_bedingt_geeignet)

    for freiwilliger in all_freiwille:
        def stelle_verfuegbar(stelle):
            freiwilliger_with_stelle = Bewerber.objects.filter(zuteilung=stelle)
            return len(freiwilliger_with_stelle) < stelle.max_freiwillige

        first_wish = freiwilliger.first_wish_einsatzstelle
        second_wish = freiwilliger.second_wish_einsatzstelle
        third_wish = freiwilliger.third_wish_einsatzstelle

        wish_list = [first_wish, second_wish, third_wish]

        for wish in wish_list:
            if wish and stelle_verfuegbar(wish):
                freiwilliger.zuteilung = wish
                freiwilliger.save()
                break

    return redirect('zuteilung')


@required_role('B')
def land(request):
    deadline = DeadlineDateTime.objects.first()

    if timezone.now() > deadline.deadline:
        message_text = 'Die Frist für die Auswahl des Einsatzlandes ist abgelaufen.'
        messages.info(request, message_text)
        return redirect('start')

    if request.method == 'POST':
        try:
            freiwilliger_instance = Bewerber.objects.get(user=request.user)
        except Bewerber.DoesNotExist:
            # Handle the case where the user does not have a Bewerber instance
            return HttpResponse('User not found', status=404)

        form = WishForm(request.POST, instance=freiwilliger_instance)
        if form.is_valid():
            # Process the data in form.cleaned_data
            form.save()

            # Redirect to a new URL or render a success message
            return redirect('start')
    else:
        freiwilliger_exists = Bewerber.objects.filter(user=request.user).exists()
        if not freiwilliger_exists:
            msg_text = 'Du bist kein Bewerber/keine Bewerberin. Bitte einen anderen Login nutzen'
            messages.info(request, msg_text)
            return redirect('start')
        form = WishForm(instance=Bewerber.objects.get(user=request.user))
        deadline_hour_left = int((deadline.deadline - timezone.now()).total_seconds() // 3600)
    return render(request, 'land.html', {'form': form, 'deadline_hour_left': deadline_hour_left})
