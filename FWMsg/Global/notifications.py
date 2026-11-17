"""
Central registry and dispatch for per-user notification preferences.

Every notification that is sent to an individual user (email and/or web push)
is described by a ``NotificationType``. Users can switch each channel on or off
per type; the choice is stored in ``Global.models.NotificationPreference``. A
missing row means "use the default from the registry", so new users and new
notification types need no data migration.

``CustomUser.mail_notifications`` stays the global master switch for emails.
"""
import logging
from dataclasses import dataclass, field

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

logger = logging.getLogger(__name__)

EMAIL = 'email'
PUSH = 'push'
CHANNELS = (EMAIL, PUSH)


class NotificationType(models.TextChoices):
    POST = 'post', _('Posts')
    CHAT_DIRECT = 'chat_direct', _('Direktnachricht')
    CHAT_GROUP = 'chat_group', _('Gruppennachricht')
    CALENDAR_NEW = 'calendar_new', _('Neuer Kalendereintrag')
    TASK_NEW = 'task_new', _('Neue Aufgaben')
    TASK_REMINDER = 'task_reminder', _('Aufgabenerinnerung')
    AMPEL_REMINDER = 'ampel_reminder', _('Ampel-Erinnerung')
    CHANGE_REQUEST_DECISION = 'change_request_decision', _('Entscheidung über Änderungsvorschlag')
    TEAM_TASK_DONE = 'team_task_done', _('Aufgabe erledigt')
    TEAM_AMPEL_NEW = 'team_ampel_new', _('Neue Ampelmeldung')


@dataclass(frozen=True)
class NotificationSpec:
    type: str
    group: str
    description: str
    channels: tuple = CHANNELS
    defaults: dict = field(default_factory=lambda: {EMAIL: True, PUSH: True})
    # PersonCluster.view letters that may configure this type; None = everyone.
    roles: tuple = None
    # Optional PersonCluster boolean flag that must be set (e.g. 'ampel').
    cluster_flag: str = None
    # Bootstrap icon shown in the settings page
    icon: str = 'bi-bell'

    @property
    def label(self):
        return NotificationType(self.type).label

    def is_visible_for(self, user):
        if user.is_superuser:
            return True
        customuser = getattr(user, 'customuser', None)
        cluster = getattr(customuser, 'person_cluster', None) if customuser else None
        if self.roles is not None:
            if not cluster or cluster.view not in self.roles:
                return False
        if self.cluster_flag:
            if not cluster or not getattr(cluster, self.cluster_flag, False):
                return False
        return True


GROUP_COMMUNICATION = _('Kommunikation')
GROUP_ORGANISATION = _('Kalender & Aufgaben')
GROUP_TEAM = _('Organisation & Team')

NOTIFICATION_SPECS = {
    spec.type: spec for spec in [
        NotificationSpec(NotificationType.POST, GROUP_COMMUNICATION,
                         _('Neue Posts für dich und Antworten auf Posts'),
                         icon='bi-megaphone'),
        NotificationSpec(NotificationType.CHAT_DIRECT, GROUP_COMMUNICATION,
                         _('Neue Nachricht in einem Einzelchat'),
                         icon='bi-chat'),
        NotificationSpec(NotificationType.CHAT_GROUP, GROUP_COMMUNICATION,
                         _('Neue Nachricht in einem Gruppenchat'),
                         icon='bi-chat-dots'),
        NotificationSpec(NotificationType.CALENDAR_NEW, GROUP_ORGANISATION,
                         _('Wenn du zu einem Kalendereintrag eingeladen wirst'),
                         cluster_flag='calendar', icon='bi-calendar-event'),
        NotificationSpec(NotificationType.TASK_NEW, GROUP_ORGANISATION,
                         _('Wenn dir neue Aufgaben zugewiesen werden'),
                         cluster_flag='aufgaben', icon='bi-list-check'),
        NotificationSpec(NotificationType.TASK_REMINDER, GROUP_ORGANISATION,
                         _('Erinnerung an fällige Aufgaben'),
                         cluster_flag='aufgaben', icon='bi-alarm'),
        NotificationSpec(NotificationType.AMPEL_REMINDER, GROUP_ORGANISATION,
                         _('Erinnerung, eine Ampelmeldung abzugeben'),
                         cluster_flag='ampel', icon='bi-stoplights'),
        NotificationSpec(NotificationType.CHANGE_REQUEST_DECISION, GROUP_TEAM,
                         _('Wenn über deinen Änderungsvorschlag entschieden wurde'),
                         roles=('O', 'A'), icon='bi-pencil-square'),
        NotificationSpec(NotificationType.TEAM_TASK_DONE, GROUP_TEAM,
                         _('Wenn Freiwillige in deinen Ländern eine Aufgabe erledigen'),
                         roles=('T',), icon='bi-check2-circle'),
        NotificationSpec(NotificationType.TEAM_AMPEL_NEW, GROUP_TEAM,
                         _('Wenn Freiwillige in deinen Ländern eine Ampelmeldung abgeben'),
                         roles=('T',), icon='bi-stoplights'),
    ]
}


def get_spec(notification_type):
    return NOTIFICATION_SPECS[str(notification_type)]


def _get_preference(user, notification_type):
    from Global.models import NotificationPreference
    # Use a per-instance cache so loops over many types hit the DB only once.
    cache = getattr(user, '_notification_pref_cache', None)
    if cache is None:
        cache = {p.notification_type: p for p in NotificationPreference.objects.filter(user=user)}
        user._notification_pref_cache = cache
    return cache.get(str(notification_type))


def get_channel_setting(user, notification_type, channel):
    """The user's own choice for one type/channel (ignores the master switch)."""
    spec = get_spec(notification_type)
    if channel not in spec.channels:
        return False
    pref = _get_preference(user, notification_type)
    if pref is not None:
        return getattr(pref, channel)
    return spec.defaults.get(channel, False)


def wants_notification(user, notification_type, channel):
    """True if ``user`` should get ``notification_type`` via ``channel``."""
    if user is None:
        return False
    if channel == EMAIL:
        customuser = getattr(user, 'customuser', None)
        if customuser is not None and not customuser.mail_notifications:
            return False
        if not user.email:
            return False
    return get_channel_setting(user, notification_type, channel)


def set_preference(user, notification_type, channel, enabled):
    from Global.models import NotificationPreference
    spec = get_spec(notification_type)
    if channel not in spec.channels:
        raise ValueError(f'Channel {channel} not available for {notification_type}')
    pref = _get_preference(user, notification_type)
    if pref is None:
        pref = NotificationPreference(
            user=user,
            org=user.customuser.org,
            notification_type=str(notification_type),
            email=spec.defaults.get(EMAIL, False),
            push=spec.defaults.get(PUSH, False),
        )
    setattr(pref, channel, bool(enabled))
    pref.save()
    if hasattr(user, '_notification_pref_cache'):
        user._notification_pref_cache[str(notification_type)] = pref
    return pref


def filter_users_wanting(users_qs, notification_type, channel):
    """Restrict a ``User`` queryset to users who want the notification via ``channel``."""
    spec = get_spec(notification_type)
    if channel not in spec.channels:
        return users_qs.none()
    explicit_off = {'notification_preferences__notification_type': str(notification_type),
                    f'notification_preferences__{channel}': False}
    explicit_on = {'notification_preferences__notification_type': str(notification_type),
                   f'notification_preferences__{channel}': True}
    if spec.defaults.get(channel, False):
        qs = users_qs.exclude(id__in=users_qs.model.objects.filter(**explicit_off).values('id'))
    else:
        qs = users_qs.filter(id__in=users_qs.model.objects.filter(**explicit_on).values('id'))
    if channel == EMAIL:
        qs = qs.filter(customuser__mail_notifications=True).exclude(email__isnull=True).exclude(email='')
    return qs


def visible_specs_for(user):
    return [spec for spec in NOTIFICATION_SPECS.values() if spec.is_visible_for(user)]


def notify_user(user, notification_type, subject, *, email_html=None, push_body=None,
                url=None, reply_to=None, tag=None):
    """
    Send one notification to one user, respecting their preferences.

    Email and push are decided independently. Returns a dict
    ``{'email': bool, 'push': int}`` with what was actually sent.
    """
    # Resolved through Global.send_email so a single patch target covers both
    # channels in tests (send_email re-exports send_push_notification_to_user).
    from Global import send_email as mailer

    result = {EMAIL: False, PUSH: 0}

    if email_html is not None and wants_notification(user, notification_type, EMAIL):
        try:
            try:
                unsubscribe_url = get_type_unsubscribe_url(user, notification_type)
            except Exception as e:
                logger.warning(f'No unsubscribe URL for user {user.id}: {e}')
                unsubscribe_url = None
            result[EMAIL] = bool(mailer.send_email_with_archive(
                subject, mailer.html_to_text(email_html), settings.SERVER_EMAIL, [user.email],
                html_message=email_html, reply_to_list=reply_to,
                unsubscribe_url=unsubscribe_url,
            ))
        except Exception as e:
            logger.error(f'Error sending {notification_type} email to user {user.id}: {e}')

    if push_body is not None and wants_notification(user, notification_type, PUSH):
        try:
            result[PUSH] = mailer.send_push_notification_to_user(user, subject, push_body, tag=tag, url=url)
        except Exception as e:
            logger.error(f'Error sending {notification_type} push to user {user.id}: {e}')

    return result


def get_type_unsubscribe_url(user, notification_type):
    """Unsubscribe link that only switches off emails for one notification type."""
    base = user.customuser.get_unsubscribe_url()
    return f'{base}?type={notification_type}'
