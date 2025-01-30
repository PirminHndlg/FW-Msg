import datetime

from django import template
from datetime import date
from django.db.models import ManyToManyField

register = template.Library()


@register.filter
def get_attribute(obj, attr):
    """Get an attribute of an object by name."""
    return getattr(obj, attr, '')

@register.filter
def getattribute(obj, attr):
    """Get an attribute of an object by name."""
    return getattr(obj, attr, '')

@register.filter
def get_fields(obj):
    """Get the fields of an object."""
    return obj.fields

@register.filter
def is_many_to_many(obj, field_name):
    """Check if a field is a many-to-many relationship."""
    try:
        field = obj._meta.get_field(field_name)
        return isinstance(field, ManyToManyField)
    except:
        return False

@register.filter
def get_field_type(obj, field_name):
    """Return the field type name for a given model field."""
    try:
        field = obj._meta.get_field(field_name)
        return field.get_internal_type()
    except:
        return ''

@register.filter
def include(value, substring):
    """Check if a string contains a substring."""
    if isinstance(value, str) and isinstance(substring, str) and value and substring:
        return substring in value
    return False
