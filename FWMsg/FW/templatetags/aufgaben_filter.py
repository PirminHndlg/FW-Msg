from datetime import datetime, timezone

from django import template
from django.utils.safestring import mark_safe
from django.urls import reverse
from django.template.loader import render_to_string
from django.utils import timezone as django_timezone

register = template.Library()

@register.filter
def compare_date_to_current_time(date):
    return date < django_timezone.now().date() if date else False

@register.filter
def old_generate_html_for_aufgaben(aufgaben):
    """Render a grid of task cards."""
    return render_to_string('components/task_grid.html', {
        'tasks': aufgaben,
        'now': django_timezone.now()
    })