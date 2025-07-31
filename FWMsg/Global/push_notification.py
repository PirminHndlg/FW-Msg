import json
import logging
from datetime import datetime

from django.conf import settings
from django.utils import timezone
from pywebpush import webpush, WebPushException

logger = logging.getLogger(__name__)

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
        "title": title,
        "body": body,
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
            data=json.dumps(data),
            vapid_private_key=settings.VAPID_PRIVATE_KEY,
            vapid_claims={
                "sub": f"mailto:{settings.SERVER_EMAIL}"
            }
        )
        
        # Update last_used timestamp if successful
        subscription.last_used = timezone.now()
        subscription.save(update_fields=['last_used'])
        return True
    except WebPushException as e:
        # If the subscription is no longer valid (404), delete it
        if e.response and e.response.status_code == 404:
            logger.info(f"Removing expired push subscription for user {subscription.user.username}")
            subscription.delete()
        else:
            logger.error(f"WebPushException: {str(e)}")
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