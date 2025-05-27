from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    return dictionary.get(key) 

@register.filter
def max_order(questions):
    return questions.order_by('order').last().order