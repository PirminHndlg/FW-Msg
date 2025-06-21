import re
from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

from Global.models import CustomUser

register = template.Library()
