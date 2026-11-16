import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from Global.models import PushSubscription
from Global.notifications import (
    CHANNELS,
    EMAIL,
    GROUP_COMMUNICATION,
    GROUP_ORGANISATION,
    GROUP_TEAM,
    NOTIFICATION_SPECS,
    PUSH,
    get_channel_setting,
    set_preference,
    visible_specs_for,
)
from Global.views import check_organization_context

GROUP_ICONS = {
    str(GROUP_COMMUNICATION): 'bi-chat-square-text',
    str(GROUP_ORGANISATION): 'bi-calendar-check',
    str(GROUP_TEAM): 'bi-building',
}


@login_required
def notification_settings(request):
    """Per-type email/push preferences of the current user."""
    groups = {}
    for spec in visible_specs_for(request.user):
        group = groups.setdefault(str(spec.group), {
            'name': spec.group,
            'icon': GROUP_ICONS.get(str(spec.group), 'bi-bell'),
            'items': [],
        })
        group['items'].append({
            'type': spec.type,
            'label': spec.label,
            'description': spec.description,
            'icon': spec.icon,
            'has_email': EMAIL in spec.channels,
            'has_push': PUSH in spec.channels,
            'email': get_channel_setting(request.user, spec.type, EMAIL),
            'push': get_channel_setting(request.user, spec.type, PUSH),
        })

    customuser = getattr(request.user, 'customuser', None)
    context = check_organization_context(request, {
        'notification_groups': list(groups.values()),
        'mail_master_enabled': customuser.mail_notifications if customuser else True,
        'has_push_subscription': PushSubscription.objects.filter(user=request.user).exists(),
    })
    return render(request, 'notification_settings.html', context=context)


@login_required
@require_POST
def update_notification_preference(request):
    try:
        data = json.loads(request.body)
    except (ValueError, TypeError):
        return JsonResponse({'success': False, 'error': _('Ungültige Anfrage')}, status=400)

    notification_type = data.get('type')
    channel = data.get('channel')
    enabled = data.get('enabled')

    spec = NOTIFICATION_SPECS.get(notification_type)
    if (spec is None or channel not in CHANNELS or channel not in spec.channels
            or not isinstance(enabled, bool) or not spec.is_visible_for(request.user)):
        return JsonResponse({'success': False, 'error': _('Ungültige Anfrage')}, status=400)
    if not hasattr(request.user, 'customuser'):
        return JsonResponse({'success': False, 'error': _('Kein Benutzerprofil')}, status=400)

    set_preference(request.user, notification_type, channel, enabled)
    return JsonResponse({'success': True, 'type': notification_type, 'channel': channel, 'enabled': enabled})
