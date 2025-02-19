import re
from django import template

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
    links = re.findall(r'https?://\S+', text)
    for link in links:
        text = text.replace(link, f'<a href="{link}" target="_blank">{link}</a>')
    links_2 = re.findall(r'www\.\S+', text)
    for link in links_2:
        text = text.replace(link, f'<a href="https://{link}" target="_blank">{link}</a>')
    emails = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b', text)
    for email in emails:
        text = text.replace(email, f'<a href="mailto:{email}" target="_blank">{email}</a>')
    # Remove spaces, parentheses and hyphens before searching for phone numbers
    cleaned_text = re.sub(r'[\s\(\)\-]', '', text)
    tel_numbers = re.findall(r'\+\d{10,15}', cleaned_text)
    for tel_number in tel_numbers:
        # Find the original phone number format in the text by looking for the digits
        original_number = ''
        digit_pos = 0
        for char in text:
            if digit_pos < len(tel_number) and char == tel_number[digit_pos]:
                original_number += char
                digit_pos += 1
            elif char in ' ()-' and digit_pos > 0 and digit_pos < len(tel_number):
                original_number += char
        text = text.replace(original_number, f'<a href="tel:{tel_number}" target="_blank">{original_number}</a>')
    line_breaks = re.findall(r'\n', text)
    for line_break in line_breaks:
        text = text.replace(line_break, '<br>')
    return text
