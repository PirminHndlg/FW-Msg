from django import template

register = template.Library()

@register.filter
def is_numeric(value):
    """Check if a value is numeric."""
    try:
        float(value)
        return True
    except ValueError:
        return False