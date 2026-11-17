from django import template
from django.contrib import admin

register = template.Library()


@register.simple_tag
def admin_site_header() -> str:
    return admin.site.site_header
