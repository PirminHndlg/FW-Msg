from django import template

register = template.Library()

@register.filter
def filter_person_cluster(person_cluster):
    return person_cluster.filter(view='F')

