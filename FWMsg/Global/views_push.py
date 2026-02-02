import json
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.urls import reverse
from django.contrib import messages
from .models import PushSubscription
from .push_notification import get_vapid_public_key, send_push_notification_to_user

from Global.views import check_organization_context

@login_required
def push_settings(request):
    """
    View for managing push notification settings.
    Displays a list of registered devices and allows testing notifications.
    """
    subscriptions = PushSubscription.objects.filter(user=request.user, org=request.user.org)
    
    # If a test notification was requested
    if request.method == 'POST' and 'send_test' in request.POST:
        success_count = send_push_notification_to_user(
            request.user,
            'Test Benachrichtigung',
            'Dies ist eine Testbenachrichtigung von Volunteer.Solutions.',
            url=request.build_absolute_uri(reverse('push_settings')),
        )
        
        if success_count > 0:
            if success_count == 1:
                messages.success(request, 'Testbenachrichtigung wurde an 1 Gerät gesendet.')
            else:
                messages.success(request, f'Testbenachrichtigung wurde an {success_count} Gerät(e) gesendet.')
        else:
            messages.error(request, 'Testbenachrichtigung konnte nicht gesendet werden. Bitte prüfe Deine Browser-Einstellungen.')

        return redirect('push_settings')
    
    vapid_public_key = get_vapid_public_key()

    context = {
        'subscriptions': subscriptions,
        'vapid_public_key': vapid_public_key
    }
    context = check_organization_context(request, context)
    return render(request, 'push_settings.html', context)

@login_required
def remove_subscription(request, subscription_id):
    """
    View to remove a push subscription.
    """
    try:
        subscription = PushSubscription.objects.get(
            id=subscription_id,
            user=request.user,
            org=request.user.org
        )
        subscription.delete()
        return redirect('push_settings')
    except PushSubscription.DoesNotExist:
        return redirect('push_settings')

@login_required
@require_POST
@csrf_exempt
def save_subscription(request):
    """
    View to save a push subscription from the browser.
    """
    try:
        data = json.loads(request.body)
        
        if not all(k in data for k in ['endpoint', 'keys']):
            return JsonResponse({'status': 'error', 'message': 'Invalid subscription data'}, status=400)
        
        # Check if we already have this subscription
        subscription, created = PushSubscription.objects.get_or_create(
            user=request.user,
            org=request.user.org,
            endpoint=data['endpoint'],
            defaults={
                'p256dh': data['keys']['p256dh'],
                'auth': data['keys']['auth'],
                'name': data.get('name', f'Browser auf {request.META.get("HTTP_USER_AGENT", "Unbekannt")}')
            }
        )
        
        # If subscription existed but keys changed, update them
        if not created and (
            subscription.p256dh != data['keys']['p256dh'] or 
            subscription.auth != data['keys']['auth']
        ):
            subscription.p256dh = data['keys']['p256dh']
            subscription.auth = data['keys']['auth']
            subscription.save()
        
        return JsonResponse({
            'status': 'success', 
            'message': 'Subscription saved successfully',
            'created': created
        })
        
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@login_required
@require_GET
def vapid_public_key(request):
    """
    View to get the VAPID public key.
    """
    return JsonResponse({
        'publicKey': get_vapid_public_key()
    }) 

@login_required
@require_GET
def service_worker(request):
    """
    View to serve the service worker file.
    """
    with open('Global/global-static/js/service-worker.js', 'r') as f:
        return HttpResponse(f.read(), content_type='application/javascript')
    
@login_required
@require_GET
def test_notification(request):
    """
    View to test push notifications.
    """
    try:
        from .push_notification import send_push_notification_to_user
        success_count = send_push_notification_to_user(
            request.user,
            'Test Benachrichtigung',
            'Dies ist eine Testbenachrichtigung von Volunteer.Solutions.',
        )
        return JsonResponse({
            'status': 'success',
            'message': f'Testbenachrichtigung wurde an {success_count} Gerät(e) gesendet.'
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
