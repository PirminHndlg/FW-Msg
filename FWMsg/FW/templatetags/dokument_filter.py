from django import template

register = template.Library()

@register.filter
def starts_with(value, arg):
    print('value', value)
    return value.startswith(arg)

@register.filter
def ends_with(value, arg):
    return value.endswith(arg)

@register.filter
def get_document_name(value):
    if hasattr(value, 'dokument'):
        return value.dokument.name.split('/')[-1]
    return value