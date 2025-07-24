from django import template
from django.forms import widgets

register = template.Library()

@register.filter
def widget_type(field):
    """Get the widget type name for a form field"""
    widget = field.field.widget
    return widget.__class__.__name__

@register.filter
def is_checkbox_widget(field):
    """Check if field uses checkbox widget"""
    return isinstance(field.field.widget, (widgets.CheckboxSelectMultiple,))

@register.filter
def is_radio_widget(field):
    """Check if field uses radio widget"""
    return isinstance(field.field.widget, (widgets.RadioSelect,))

@register.filter
def is_select_widget(field):
    """Check if field uses select widget"""
    return isinstance(field.field.widget, (widgets.Select,))

@register.filter
def is_textarea_widget(field):
    """Check if field uses textarea widget"""
    return isinstance(field.field.widget, (widgets.Textarea,))

@register.filter
def has_choices(field):
    """Check if field has choices (for select, radio, checkbox)"""
    return hasattr(field.field, 'choices') and field.field.choices 