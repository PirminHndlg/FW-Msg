from django import template

register = template.Library()

@register.filter
def get_my_reaction(bild, user):
    return bild.get_my_reaction(user)