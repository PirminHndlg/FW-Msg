from django import template

from ..models import CustomUser

register = template.Library()

@register.filter
def hex_to_rgb(hex_code):
    hex_code = hex_code.lstrip('#')
    r, g, b = tuple(int(hex_code[i:i+2], 16) for i in (0, 2, 4))
    return f"{r}, {g}, {b}"

@register.filter
def get_color(user):
    org = get_org(user)
    if org:
        return org.farbe
    return '#007bff'

@register.filter
def get_secondary_color(user):
    org = get_org(user)
    if org:
        return org.farbe
    return '#10700f'

@register.filter
def get_text_color(user):
    org = get_org(user)
    color = 'black'
    # if org:
    #     color = org.farbe
    # else:
    #     color = 'green'
    return color

@register.filter
def get_org(user):
    if user.is_authenticated:
        if CustomUser.objects.filter(user=user).exists():
            return CustomUser.objects.get(user=user).org
    return None

@register.filter
def get_date(value):
    return value.strftime('%d.%m.%Y')