from django import template

from ..models import Freiwilliger

register = template.Library()

@register.filter
def get_color(user):
    freiwilliger = Freiwilliger.objects.get(user=user)
    if freiwilliger:
        color = freiwilliger.org.farbe
    else:
        color = 'green'
    return color

@register.filter
def get_secondary_color(user):
    freiwilliger = Freiwilliger.objects.get(user=user)
    if freiwilliger:
        color = freiwilliger.org.farbe
    else:
        color = 'green'
    return color

@register.filter
def get_logo(user):
    freiwilliger = Freiwilliger.objects.get(user=user)
    if freiwilliger:
        logo = freiwilliger.org.logo
    else:
        logo = None
    return logo