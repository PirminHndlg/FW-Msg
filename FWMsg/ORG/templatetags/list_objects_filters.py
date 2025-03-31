import datetime

from django import template
from datetime import date
from django.db.models import ManyToManyField
import re
from django.db import models
from django.utils.html import format_html

register = template.Library()


@register.filter
def get_attribute(obj, field):
    """Get an attribute of an object dynamically from a string name"""
    if hasattr(obj, str(field.get('name'))):
        attr = getattr(obj, field.get('name'))
        if field.get('type') == 'D':
            try:
                return datetime.datetime.strptime(attr, '%Y-%m-%d').date()
            except ValueError:
                return attr
        return attr
    elif hasattr(obj, 'get_%s_display' % field.get('name')):
        print('2', getattr(obj, 'get_%s_display' % field.get('name'))())
        return getattr(obj, 'get_%s_display' % field.name)()
    return None

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
    """Check if a field is a many-to-many relationship"""
    try:
        return isinstance(obj._meta.get_field(field_name), models.ManyToManyField)
    except:
        return False

@register.filter
def get_field_type(obj, field):
    """Get the field type of a model field"""
    try:
        return obj._meta.get_field(field.get('name')).get_internal_type()
    except:
        match field.get('type'):
            case 'T':
                return 'CharField'
            case 'L':
                return 'TextField'
            case 'N':
                return 'IntegerField'
            case 'B':
                return 'BooleanField'
            case 'E':
                return 'EmailField'
            case 'P':
                return 'PhoneNumberField'
            case 'C':
                return 'ChoiceField'
            case 'D':
                return 'DateField'
            case 'P':
                return 'PhoneNumberField'
            case _:
                return None

        

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

@register.filter
def has_choices(obj, field):
    """Check if a field has choices defined"""
    try:
        field = obj._meta.get_field(field.get('name'))
        return bool(field.choices)
    except:
        if field.get('type'):
            return field.get('type') == 'B'
        return False

@register.filter
def get_choice_label(obj, field):
    """Get the display label for a choice field"""
    if hasattr(obj, f'get_{field.get("name")}_display'):
        return getattr(obj, f'get_{field.get("name")}_display')()
    return get_attribute(obj, field)
