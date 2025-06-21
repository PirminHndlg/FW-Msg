from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe
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
    
    # First escape the text to prevent XSS
    text = escape(text)
    
    # Convert URLs to links
    links = re.findall(r'https?://\S+', text)
    for link in links:
        safe_link = escape(link)
        target = 'target="_blank"' if not link.startswith("https://volunteer.solutions") else ""
        text = text.replace(safe_link, f'<a href="{safe_link}" class="text-decoration-underline text-body" {target}>{safe_link}</a>')
    
    # Convert www URLs to links
    links_2 = re.findall(r'www\.\S+', text)
    for link in links_2:
        safe_link = escape(link)
        target = 'target="_blank"' if not link.startswith("www.volunteer.solutions") else ""
        text = text.replace(safe_link, f'<a href="https://{safe_link}" class="text-decoration-underline text-body" {target}>{safe_link}</a>')
    
    # Convert emails to mailto links
    emails = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b', text)
    for email in emails:
        safe_email = escape(email)
        text = text.replace(safe_email, f'<a href="mailto:{safe_email}" class="text-decoration-underline text-body" target="_blank">{safe_email}</a>')
    
    # Convert phone numbers to tel links
    # Remove spaces, parentheses and hyphens before searching for phone numbers
    cleaned_text = re.sub(r'[\s\(\)\-]', '', str(text))
    tel_numbers = re.findall(r'\+\d{10,15}', cleaned_text)
    for tel_number in tel_numbers:
        # Find the original phone number format in the text by looking for the digits
        original_number = ''
        digit_pos = 0
        for char in str(text):
            if digit_pos < len(tel_number) and char == tel_number[digit_pos]:
                original_number += char
                digit_pos += 1
            elif char in ' ()-' and digit_pos > 0 and digit_pos < len(tel_number):
                original_number += char
        if original_number:
            safe_tel = escape(tel_number)
            safe_original = escape(original_number)
            text = text.replace(safe_original, f'<a href="tel:{safe_tel}" class="text-decoration-underline text-body" target="_blank">{safe_original}</a>')
    
    # Convert line breaks to <br>
    text = text.replace('\n', '<br>')
    
    # Mark the result as safe since we've properly escaped everything
    return mark_safe(text)

@register.filter
def get_date(value):
    return value.strftime('%d.%m.%Y')

@register.filter
def split(value, separator):
    return value.split(separator)