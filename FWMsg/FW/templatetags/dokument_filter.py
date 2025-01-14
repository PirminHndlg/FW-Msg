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

@register.filter
def get_short_link(value):
    try:
        from urllib.parse import urlparse
        parsed = urlparse(value)
        return parsed.netloc
    except:
        return value
    
@register.filter
def get_favicon_url(value):
    return f"https://{get_short_link(value)}/favicon.ico"