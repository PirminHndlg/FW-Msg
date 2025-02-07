from datetime import datetime, timezone

from django import template
from django.utils.safestring import mark_safe
from django.urls import reverse

register = template.Library()

@register.filter
def generate_html_for_aufgaben(aufgaben):
    html_content = ""
    html_content += '<div class="row row-cols-1 row-cols-md-3 g-4">'
    for aufgabe in aufgaben:
        detail_url = reverse("aufgaben_detail", args=[aufgabe.id])
        html_content += '<div class="col">'
        html_content += '<div class="card h-100 rounded-4">'
        html_content += '<div class="card-body">'
        html_content += f'<h4 class="card-title">{aufgabe.aufgabe.name}</h4>'
        html_content += f'<p class="card-text">{aufgabe.aufgabe.beschreibung}</p>'
        if aufgabe.faellig:
            html_content += f'<p class="card-text"><small class="text-muted">Fällig: {aufgabe.faellig.strftime("%d.%m.%Y")}</small></p>'

        if aufgabe.faellig and datetime.combine(aufgabe.faellig, datetime.min.time(), timezone.utc) < datetime.now(timezone.utc) and not aufgabe.erledigt and not aufgabe.pending:
            html_content += '<p class="card-text"><span class="badge bg-danger">Überfällig</span></p>'

        if aufgabe.erledigt:
            html_content += '<p class="card-text"><span class="badge bg-success">Erledigt</span></p>'
            html_content += f'<a href="{detail_url}" class="btn btn-success text-white">Anzeigen</a>'
        elif aufgabe.pending:
            html_content += '<p class="card-text"><span class="badge bg-warning text-dark">Wird bearbeitet</span></p>'
            html_content += f'<a href="{detail_url}" class="btn btn-primary text-white">Bearbeiten</a>'
        else:
            html_content += f'<a href="{detail_url}" class="btn btn-success text-white">Jetzt erledigen</a>'

        html_content += '</div></div></div>'
    html_content += '</div>'
    return mark_safe(html_content)