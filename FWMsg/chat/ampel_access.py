"""Access control for Ampel2 data in chat (org/team replies to volunteers)."""

from Global.models import Ampel2


def _user_org_id(user):
    org = getattr(user, "org", None)
    return org.pk if org else None


def user_is_ampel_staff(user):
    return getattr(user, "role", None) in ("O", "T")


def user_can_view_ampel(user, ampel):
    """O/T may view ampels in their org; others only their own."""
    if ampel is None:
        return False
    org_id = _user_org_id(user)
    if user_is_ampel_staff(user) and ampel.org_id == org_id:
        return True
    return ampel.user_id == user.pk


def user_can_view_ampel_by_owner(user, ampel_user_id, org_id):
    if ampel_user_id is None or org_id is None:
        return False
    if user_is_ampel_staff(user) and _user_org_id(user) == org_id:
        return True
    return user.pk == ampel_user_id


def user_can_reply_to_ampel_in_direct_chat(user, ampel, chat):
    """Only O/T may attach an ampel; it must belong to the other chat participant."""
    if ampel is None or chat is None:
        return False
    if not user_is_ampel_staff(user):
        return False
    if ampel.org_id != _user_org_id(user):
        return False
    return chat.users.filter(pk=ampel.user_id).exclude(pk=user.pk).exists()


def resolve_ampel(org, ampel_id):
    if not ampel_id:
        return None
    try:
        return Ampel2.objects.get(pk=ampel_id, org=org)
    except (Ampel2.DoesNotExist, ValueError, TypeError):
        return None


def resolve_ampel_for_direct_reply(user, ampel_id, chat):
    ampel = resolve_ampel(user.org, ampel_id)
    if user_can_reply_to_ampel_in_direct_chat(user, ampel, chat):
        return ampel
    return None
