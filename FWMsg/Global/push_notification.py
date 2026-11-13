import json
import logging
from datetime import datetime

from django.conf import settings
from django.utils import timezone
from pywebpush import webpush, WebPushException

logger = logging.getLogger(__name__)

# How long push services keep a message for an unreachable device.
PUSH_TTL_SECONDS = 24 * 60 * 60
# HTTP timeout per push request (seconds).
PUSH_REQUEST_TIMEOUT_SECONDS = 10
# Web Push payloads are limited to ~4 KB after encryption; keep well below.
PUSH_TITLE_MAX_CHARS = 120
PUSH_BODY_MAX_CHARS = 300


def _truncate(text, max_chars):
    if text is None:
        return text
    text = str(text)
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "…"

def generate_vapid_keys():
    """
    Generate VAPID keys for web push notifications.
    This function should be run once to generate the keys and then the keys should be stored in settings.
    """
    from py_vapid import Vapid
    vapid = Vapid()
    vapid.generate_keys()
    return {
        'public_key': vapid.public_key,
        'private_key': vapid.private_key
    }

def get_vapid_public_key():
    """
    Get the VAPID public key from settings.
    If not configured, generate new keys and give instructions on how to configure them.
    """
    
    if hasattr(settings, 'VAPID_PUBLIC_KEY') and settings.VAPID_PUBLIC_KEY:
        return settings.VAPID_PUBLIC_KEY
    
    from cryptography.hazmat.primitives import serialization
    
    # If keys are not configured, generate them and log instructions
    keys = generate_vapid_keys()
    public_key = keys['public_key'].public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    ).hex()
    
    private_key = keys['private_key'].private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    ).hex()
    
    logger.warning(
        "\nVAPID keys not found in settings. Please add the following to your settings.py:\n"
        f"VAPID_PUBLIC_KEY = '{public_key}'\n" 
        f"VAPID_PRIVATE_KEY = '{private_key}'\n"
    )
    return public_key

def send_push_notification(subscription, title, body, tag=None, url=None, icon=None):
    """
    Send a push notification to a single subscription.
    
    Args:
        subscription: A PushSubscription instance
        title: The notification title
        body: The notification message body
        tag: Optional string to group notifications (will replace older ones with same tag)
        url: Optional URL to open when the notification is clicked
        icon: Optional URL to an icon to display with the notification
    
    Returns:
        Boolean indicating if the notification was sent successfully
    """
    if not hasattr(settings, 'VAPID_PRIVATE_KEY') or not settings.VAPID_PRIVATE_KEY:
        logger.error("Cannot send push notification: VAPID_PRIVATE_KEY not configured in settings")
        return False
        
    subscription_info = {
        "endpoint": subscription.endpoint,
        "expirationTime": None,
        "keys": {
            "p256dh": subscription.p256dh,
            "auth": subscription.auth
        }
    }
    
    data = {
        "title": _truncate(title, PUSH_TITLE_MAX_CHARS),
        "body": _truncate(body, PUSH_BODY_MAX_CHARS),
        "requireInteraction": True
    }
    
    # Add optional parameters if provided
    if tag:
        data["tag"] = tag
    if url:
        data["url"] = url
    if icon:
        data["icon"] = icon
    
    try:
        webpush(
            subscription_info=subscription_info,
            # ensure_ascii=False keeps umlauts/emoji as UTF-8 instead of
            # 6-byte \uXXXX escapes, which matters for the ~4 KB payload limit.
            data=json.dumps(data, ensure_ascii=False),
            vapid_private_key=settings.VAPID_PRIVATE_KEY,
            vapid_claims={
                "sub": f"mailto:{settings.SERVER_EMAIL}"
            },
            # Without a TTL (pywebpush default: 0) push services drop the
            # message if the device is not reachable at that very moment.
            ttl=PUSH_TTL_SECONDS,
            headers={"Urgency": "high"},
            # pywebpush default is no timeout; a hanging endpoint would block
            # the whole fan-out loop for all remaining recipients.
            timeout=PUSH_REQUEST_TIMEOUT_SECONDS,
        )

        # Update last_used timestamp if successful
        subscription.last_used = timezone.now()
        subscription.save(update_fields=['last_used'])
        return True
    except WebPushException as e:
        # Note: requests.Response is falsy for 4xx/5xx, so compare against None.
        status_code = e.response.status_code if e.response is not None else None
        if status_code in (404, 410):
            # Subscription expired or was revoked by the browser.
            logger.info(f"Removing expired push subscription for user {subscription.user.username}")
            subscription.delete()
        else:
            logger.error(f"WebPushException (status {status_code}) for user {subscription.user.username}: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"Error sending push notification: {str(e)}")
        return False

def send_push_notification_to_user(user, title, body, tag=None, url=None, icon=None):
    """
    Send a push notification to all devices of a specific user.
    
    Args:
        user: The User to send notifications to
        title: The notification title
        body: The notification message body
        tag: Optional string to group notifications
        url: Optional URL to open when the notification is clicked
        icon: Optional URL to an icon to display
        
    Returns:
        Number of devices the notification was successfully sent to
    """
    # Import PushSubscription here to avoid circular imports
    from Global.models import PushSubscription
    
    subscriptions = PushSubscription.objects.filter(user=user)
    print(f"Sending push notification to {len(subscriptions)} devices")
    success_count = 0
    
    for subscription in subscriptions:
        if send_push_notification(subscription, title, body, tag, url, icon):
            success_count += 1
            
    return success_count 