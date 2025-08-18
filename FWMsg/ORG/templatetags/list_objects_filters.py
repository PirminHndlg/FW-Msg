import datetime

from django import template
from django.db import models

register = template.Library()


@register.filter
def get_attribute(obj, field):
    """Get an attribute of an object dynamically from a string name"""
    if hasattr(obj, str(field.get('name'))):
        attr = getattr(obj, field.get('name'))
        if field.get('type') == 'D':
            if isinstance(attr, datetime.datetime):
                return attr.date()
            elif attr is None:
                return ''
            else:
                try:
                    return datetime.datetime.strptime(attr, '%Y-%m-%d').date()
                except:
                    return attr
        return attr
    elif hasattr(obj, 'get_%s_display' % field.get('name').replace(' ', '_')):
        return getattr(obj, 'get_%s_display' % field.get('name').replace(' ', '_'))()
    elif hasattr(obj, field.get('name').replace(' ', '_')):
        return getattr(obj, field.get('name').replace(' ', '_'))
    
    return None

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
        field_type = field.get('type')
        if field_type == 'T':
            return 'CharField'
        elif field_type == 'L':
            return 'TextField'
        elif field_type == 'N':
            return 'IntegerField'
        elif field_type == 'B':
            return 'BooleanField'
        elif field_type == 'E':
            return 'EmailField'
        elif field_type == 'P':
            return 'PhoneNumberField'
        elif field_type == 'C':
            return 'ChoiceField'
        elif field_type == 'D':
            return 'DateField'
        else:
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

@register.filter
def get_display_name(obj):
    """Get a user-friendly display name for an object"""
    # Try common name fields first
    for field in ['name', 'title', 'username', 'ordner_name', 'question_text', 'titel']:
        if hasattr(obj, field) and getattr(obj, field):
            return getattr(obj, field)
    
    # Try name combinations for users
    if hasattr(obj, 'first_name') and hasattr(obj, 'last_name'):
        first_name = getattr(obj, 'first_name')
        last_name = getattr(obj, 'last_name')
        if first_name and last_name:
            return f"{first_name} {last_name}"
        elif first_name:
            return first_name
        elif last_name:
            return last_name
    
    # Try user relation
    if hasattr(obj, 'user'):
        user = getattr(obj, 'user')
        if hasattr(user, 'first_name') and hasattr(user, 'last_name'):
            return f"{user.first_name} {user.last_name}" if user.first_name and user.last_name else user.username
    
    # Fall back to string representation
    return str(obj)
