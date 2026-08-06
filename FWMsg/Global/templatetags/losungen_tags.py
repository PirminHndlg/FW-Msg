from datetime import date

from django import template

from ..losungen import Losung, get_losung_for_date, get_todays_losung


register = template.Library()


@register.simple_tag
def todays_losung() -> Losung | None:
    """Return today's Losung as a dictionary or None."""
    return get_todays_losung()


@register.simple_tag
def losung_for_date(losung_date: date) -> Losung | None:
    """Return the Losung for a given date object or None."""
    return get_losung_for_date(losung_date)
