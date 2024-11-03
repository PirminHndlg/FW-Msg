from django import template

from ..models import CustomUser

register = template.Library()

@register.filter
def get_color(user):
    org = get_org(user)
    if org:
        color = org.farbe
    else:
        color = 'green'
    return color

@register.filter
def get_secondary_color(user):
    org = get_org(user)
    if org:
        color = org.farbe
    else:
        color = 'green'
    return color

@register.filter
def get_org(user):
    if user.is_authenticated:
        if CustomUser.objects.filter(user=user).exists():
            return CustomUser.objects.get(user=user).org
    return None