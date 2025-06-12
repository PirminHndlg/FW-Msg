import re
from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

from Global.models import CustomUser

register = template.Library()


@register.filter
def split(value, separator):
    print(value, separator)
    print(value.split(separator))
    return value.split(separator)

@register.filter
def get_date(value):
    return value.strftime('%d.%m.%Y')

@register.filter
def add_class(field, class_name):
    return field.as_widget(attrs={"class": class_name})

@register.filter
def get_auswaeriges_amt_link(value):
    """Convert German special characters to their ASCII equivalents for URLs."""
    replacements = {
        'ä': 'ae',
        'ö': 'oe', 
        'ü': 'ue',
        'ß': 'ss',
        'Ä': 'Ae',
        'Ö': 'Oe',
        'Ü': 'Ue'
    }
    import requests
    link = ''.join(replacements.get(c, c) for c in value.lower())
    url = f"https://www.auswaertiges-amt.de/de/service/laender/{link}-node/"
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            return url
    except:
        pass
    return 'https://www.auswaertiges-amt.de/de/reiseundsicherheit'

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
