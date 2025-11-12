from django import template
from BW.models import Bewerber

register = template.Library()

@register.filter
def max_order(questions):
    return questions.order_by('order').last().order


@register.filter
def get_bewerbers_of_interviewperson(interview_persons):
    bewerbers = Bewerber.objects.filter(interview_persons=interview_persons)
    return bewerbers