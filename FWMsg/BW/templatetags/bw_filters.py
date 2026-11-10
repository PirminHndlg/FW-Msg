from django import template
from django.db.models import F
from BW.models import Bewerber

register = template.Library()

@register.filter
def max_order(questions):
    return questions.order_by('order').last().order


@register.filter
def get_bewerbers_of_interviewperson(interview_persons):
    bewerbers = Bewerber.objects.filter(
        interview_persons=interview_persons,
        seminar_bewerber__org=F('org'),
    ).distinct()
    return bewerbers
