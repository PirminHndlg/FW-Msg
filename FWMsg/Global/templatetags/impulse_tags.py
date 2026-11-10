from django import template

from ..deeptalk import get_question_for_date


register = template.Library()


@register.simple_tag(takes_context=True)
def todays_deeptalk(context):
    """Deep-Talk-Frage des Tages für die Organisation des angemeldeten Benutzers (oder None)."""
    request = context.get('request')
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return None
    try:
        org = user.org
    except Exception:
        # z. B. Superuser ohne CustomUser
        return None
    return get_question_for_date(org)
