import datetime

from django import template
from datetime import date

register = template.Library()


@register.filter
def get_attribute(obj, attr_name):
    """Safely retrieve an attribute from an object."""
    try:
        data = getattr(obj, attr_name)
        if type(data) == date:
            return data.strftime('%d.%m.%Y')
        return data
    except AttributeError:
        return None
