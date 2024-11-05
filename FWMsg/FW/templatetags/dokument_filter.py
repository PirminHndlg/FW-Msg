from django import template

register = template.Library()

@register.filter
def starts_with(value, arg):
    print('value', value)
    return value.startswith(arg)