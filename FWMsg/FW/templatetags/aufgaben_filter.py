from datetime import datetime, timezone

from django import template
from django.utils.safestring import mark_safe
from django.urls import reverse

register = template.Library()

@register.filter
def generate_html_for_aufgaben(aufgaben):
    html_content = ""
    for aufgabe in aufgaben:
        detail_url = reverse("aufgaben_detail", args=[aufgabe.aufgabe.id])
        html_content += '<div class="aufgabe_div">'
        html_content += f'<h4>{aufgabe.aufgabe.name}</h4>'
        html_content += f'<p>{aufgabe.aufgabe.beschreibung}</p>'
        if aufgabe.faellig:
            html_content += f'<p>Fällig: {aufgabe.faellig.strftime("%d.%m.%Y")}</p>'

        if aufgabe.erledigt:
            html_content += '<p>Erledigt</p>'
        elif aufgabe.pending:
            html_content += '<p>Wird bearbeitet</p>'
            html_content += f'<a href="{detail_url}">Bearbeiten</a>'
        else:
            html_content += f'<a href="{detail_url}">Jetzt erledigen</a>'

        html_content += '</div>'
    return mark_safe(html_content)