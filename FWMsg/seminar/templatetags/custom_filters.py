# your_app/templatetags/custom_filters.py
from django import template
from django.core import signing
from django.db.models import Sum
from django.utils import timezone

from Global.models import Einsatzstelle2 as Einsatzstelle, CustomUser
from seminar.models import Seminar

register = template.Library()


@register.filter
def get_seminar(org):
    print('org', org)
    return Seminar.objects.get_or_create(org=org, defaults={'name': 'Auswahlseminar', 'description': 'Hallo Welt'})[0]


@register.filter
def get_seminar_name(seminar):
    return seminar.name


@register.filter
def get_seminar_description(seminar):
    return seminar.description




@register.filter
def add(value, arg):
    print('value', value, 'arg', arg)
    if type(value) == type(arg):
        return value + arg
    return str(value) + str(arg)


@register.filter
def range_filter(value, args="1,0"):
    # print('value', value, 'args', args)
    try:
        add, start = map(int, str(args).split(","))
    except ValueError:
        add, start = 1, 0  # Default values
    # print('add', add, 'start', start)
    # print(range(start, int(value) + add))
    return range(start, int(value) + add)


@register.filter
def is_in_group(user, group_name):
    return user.groups.filter(name=group_name).exists()


@register.filter
def get_date(value):
    return value.strftime('%d%m%Y')


@register.filter
def subtract(value, arg):
    return value - (arg or 0)


@register.filter
def myround(value, decimal_places=0):
    if value is None:
        return ''
    return round(value, decimal_places)


@register.filter
def get_item(dictionary, key):
    if not dictionary:
        return None

    if type(dictionary) is dict:
        if str(key) in dictionary:
            return dictionary[str(key)]
        elif key in dictionary:
            return dictionary[key]
        else:
            return None
    return dictionary[key]


@register.filter
def get_max_stelle(stellen):
    max = int(0)
    for stelle in stellen:
        max_anzahl = stelle[0].max_freiwillige or 0
        if max_anzahl > int(max):
            max += max_anzahl
    return max


@register.filter
def get_img_url(img):
    if img:
        return img.url
    else:
        return '/static/img/default_img.png'


@register.filter
def get_max_fw_of_land(land):
    return Einsatzstelle.objects.filter(land=land).aggregate(Sum('max_freiwillige'))['max_freiwillige__sum'] or 0


@register.filter
def get_current_fw_of_stellen(stellen):
    return sum([len(stelle[1]) for stelle in stellen])


@register.filter
def get_token(user):
    if not user:
        return ''

    custom_user = CustomUser.objects.get_or_create(user=user)[0]

    if custom_user and custom_user.token:
        token = custom_user.token
    else:
        data = {
            'user_id': user.id,
        }
        token = signing.dumps(data)
        custom_user.token = token
        custom_user.save()

    return token


@register.filter
def is_age(value):
    if not value:
        return False
    sep_2025 = timezone.datetime(2007, 9, 1, 0, 0, 0, 0)
    value_datetime = timezone.datetime(value.year, value.month, value.day, 0, 0, 0, 0)
    return value_datetime > sep_2025