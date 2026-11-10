from django import template
from django.conf import settings
from django.utils.html import escape
from django.utils.safestring import mark_safe
from datetime import timedelta
import re

register = template.Library()

@register.filter
def get_current_language(request):
    return request.LANGUAGE_CODE

@register.filter
def get_color(user):
    org = get_org(user)
    if org:
        return org.farbe
    return '#007bff'

@register.filter
def get_secondary_color(user):
    org = get_org(user)
    if org:
        return org.farbe
    return '#10700f'

@register.filter
def get_text_color(user):
    org = get_org(user)
    color = 'black'
    # if org:
    #     color = org.farbe
    # else:
    #     color = 'green'
    return color

@register.filter
def get_text_color_on_org_color(user):
    org = get_org(user)
    color = '#000000'
    if org:
        color = org.text_color_on_org_color
    return color

@register.filter
def get_org(user):
    if user.is_authenticated:
        try:
            org = user.customuser.org
            return org
        except:
            return None
    return None 

@register.filter
def hex_to_rgb(hex_code):
    hex_code = hex_code.lstrip('#')
    r, g, b = tuple(int(hex_code[i:i+2], 16) for i in (0, 2, 4))
    return f"{r}, {g}, {b}"

@register.filter
def get_base_template(user):
    if user.is_authenticated:
        role = user.person_cluster.view
        if role == 'O':
            return 'baseOrg.html'
        elif role == 'T':
            return 'teamBase.html'
        else:
            return 'baseFw.html'
    return 'base.html'

@register.filter
def mul(value, arg):
    """Multiply the value by the argument"""
    return value * arg

@register.filter
def intdiv(value, arg):
    """Integer division: value // arg"""
    return value // arg

@register.filter
def divided_by(value, arg):
    """Divide the value by the argument"""
    try:
        return int(float(value) / float(arg))
    except (ValueError, ZeroDivisionError):
        return 0

@register.filter
def reverse(value):
    return value[::-1]

@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)

@register.filter
def getattribute(obj, attr):
    """Get an attribute of an object by name."""
    return getattr(obj, attr, '')

@register.filter
def format_text_with_link(text):
    if not text:
        return ''

    # Escape HTML first to prevent XSS.
    text = str(escape(text))

    # ── Phone numbers ────────────────────────────────────────────────────────
    # Must run before URL substitution; phones don't overlap with URLs.
    cleaned_text = re.sub(r'[\s()\-]', '', text)
    tel_numbers = re.findall(r'\+\d{10,15}', cleaned_text)
    for tel_number in tel_numbers:
        original_number = ''
        digit_pos = 0
        for char in text:
            if digit_pos < len(tel_number) and char == tel_number[digit_pos]:
                original_number += char
                digit_pos += 1
            elif char in ' ()-' and 0 < digit_pos < len(tel_number):
                original_number += char
        if original_number:
            text = text.replace(
                original_number,
                f'<a href="tel:{tel_number}" class="text-decoration-underline text-body">{original_number}</a>',
                1,
            )

    # ── URLs and e-mails — single-pass replacement ───────────────────────────
    # Using one re.sub call with alternation prevents double-processing:
    # the engine scans left-to-right and never re-inspects the replacement
    # text, so already-inserted <a> tags are never matched again.
    _URL_RE = re.compile(
        r'(https?://\S+)'                                           # group 1: http/https
        r'|((?<![/\w])www\.\S+)'                                    # group 2: bare www.
        r'|(\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b)',  # group 3: e-mail
        re.IGNORECASE,
    )

    def _replace(m):
        https_url = m.group(1)
        www_url   = m.group(2)
        email     = m.group(3)

        if https_url:
            target = ' target="_blank"' if not https_url.startswith(settings.DOMAIN_HOST) else ''
            return f'<a href="{https_url}" class="text-decoration-underline text-body"{target}>{https_url}</a>'

        if www_url:
            target = ' target="_blank"' if not www_url.startswith('www.volunteer.solutions') else ''
            return f'<a href="https://{www_url}" class="text-decoration-underline text-body"{target}>{www_url}</a>'

        if email:
            return f'<a href="mailto:{email}" class="text-decoration-underline text-body">{email}</a>'

        return m.group(0)

    text = _URL_RE.sub(_replace, text)

    # Normalize line endings before converting once to <br>.
    text = re.sub(r'\r\n?', '\n', text)
    text = text.replace('\n', '<br>')

    return mark_safe(text)

@register.filter
def get_date(value):
    return value.strftime('%d.%m.%Y')

@register.filter
def split(value, separator):
    return value.split(separator)

@register.filter
def get_current_seminar(org):
    from seminar.models import Seminar
    from django.utils import timezone
    # display seminars that start one week before, during and 2 days after the end of the seminar, negative values mean that the seminar is in the past or will start in the future
    current_date = timezone.now().date()
    seminars = Seminar.objects.filter(org=org)
    seminars_to_display = []
    for seminar in seminars:
        try:
            diff_start = current_date - seminar.seminar_start  # positive if seminar has started
            diff_end = seminar.seminar_end - current_date      # positive if seminar hasn't ended
            if diff_start.days >= -7 and diff_end.days >= -2:
                seminars_to_display.append(seminar)
        except:
            continue
    return seminars_to_display