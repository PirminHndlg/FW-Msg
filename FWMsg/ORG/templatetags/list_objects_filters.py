import datetime

from django import template
from datetime import date
from django.db.models import ManyToManyField
import re

register = template.Library()


@register.filter
def get_attribute(obj, attr):
    """Get an attribute of an object by name."""
    return getattr(obj, attr, '')

@register.filter
def format_text_with_link(obj):
    """Format text with links."""
    if not obj:
        return ''
    if not isinstance(obj, str):
        return obj
    links = re.findall(r'https?://\S+', obj)
    for link in links:
        obj = obj.replace(link, f'<a href="{link}" target="_blank">{link}</a>')
    links_2 = re.findall(r' www\.\S+', obj)
    for link in links_2:
        obj = obj.replace(link, f'<a href="https://{link}" target="_blank">{link}</a>')
    emails = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b', obj)
    for email in emails:
        obj = obj.replace(email, f'<a href="mailto:{email}" target="_blank">{email}</a>')
    # Remove spaces, parentheses and hyphens before searching for phone numbers

    line_breaks = re.findall(r'\n', obj)
    for line_break in line_breaks:
        obj = obj.replace(line_break, '<br>')
    return obj


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

@register.filter
def class_name(value):
    """Return the class name of an object."""
    return value.__class__.__name__
