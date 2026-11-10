/**
 * Web Push Notification Client
 * Handles service worker registration and push notification subscription.
 */

// Check for service worker and push manager support
function isPushNotificationSupported() {
    return 'serviceWorker' in navigator && 'PushManager' in window;
}


function urlBase64ToUint8Array(base64String) {
    const padding = '='.repeat((4 - base64String.length % 4) % 4);
    const base64 = (base64String + padding)
        .replace(/-/g, '+')
        .replace(/_/g, '/');

    const rawData = window.atob(base64);
    const outputArray = new Uint8Array(rawData.length);

    for (let i = 0; i < rawData.length; ++i) {
        outputArray[i] = rawData.charCodeAt(i);
    }
    return outputArray;
}

// Used by the page to show a more helpful error when push subscription
// retrieval fails on certain browsers/ROMs.
window.__pushSubscriptionError = null;


// Request permission and subscribe to push notifications
async function subscribeToPushNotifications(publicKey) {
    if (!isPushNotificationSupported()) {
        console.error('Push notifications not supported');
        return {
            success: false,
            message: 'Push-Benachrichtigungen werden in diesem Browser nicht unterstützt.'
        };
    }

    try {
        // Register the service worker - using /service-worker.js in the root
        let swRegistration = null;
        if ("serviceWorker" in navigator) {
            try {
                swRegistration = await navigator.serviceWorker.register("/service-worker.js");
            } catch (error) {
                console.error(`Service worker registration failed: ${error}`);
                throw new Error(`Service worker registration failed: ${error.message}`);
            }
        }

        // Request notification permission
        const permission = await Notification.requestPermission();
        if (permission !== 'granted') {
            console.error('Notification permission denied');
            return {
                success: false,
                message: 'Berechtigung für Benachrichtigungen verweigert. Bitte erlaube die Benachrichtigungen in deinen Browser-Einstellungen.'
            };
        }

        // Wait for the service worker to be ready
        // const applicationServerKey = convertDataURIToBinary(publicKey)
        const applicationServerKey = urlBase64ToUint8Array(publicKey);

        // Get existing subscription
        const setUpPushPermission = async () => {
            const registration = swRegistration || await navigator.serviceWorker.ready
            
            if (!registration?.pushManager?.subscribe) {
                throw new Error('PushManager.subscribe is not available on this browser build.');
            }
            const subscription = await registration.pushManager.subscribe({
              userVisibleOnly: true,
              applicationServerKey: applicationServerKey,
            })
            return subscription
          }
          
        const subscription = await setUpPushPermission()

        if (!subscription) {
            return {
                success: false,
                message: 'Push-Abonnement konnte nicht erstellt werden.'
            };
        }

        // PushSubscription is not a plain object in all browsers; use toJSON()
        // (if available) so the server receives { endpoint, keys }.
        const payload = (typeof subscription.toJSON === 'function')
            ? subscription.toJSON()
            : subscription;

        // Send the subscription to the server
        const response = await fetch('/push/save-subscription/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken()
            },
            body: JSON.stringify(payload)
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.message || 'Failed to save subscription');
        }
        
        return {
            success: true,
            message: 'Du hast dich erfolgreich für Push-Benachrichtigungen angemeldet.'
        };
    } catch (error) {
        console.error('Error subscribing to push notifications:', error);
        return {
            success: false,
            message: `Fehler beim Anmelden für Push-Benachrichtigungen: ${error.message}`
        };
    }
}

// Check if the user is already subscribed
async function checkPushSubscription() {
    if (!isPushNotificationSupported()) {
        return null;
    }

    window.__pushSubscriptionError = null;

    try {
        // getRegistration() behavior can differ per browser; try common scopes first,
        // then fall back to getRegistrations().
        let registration =
            await navigator.serviceWorker.getRegistration() ||
            await navigator.serviceWorker.getRegistration('/');

        if (!registration && navigator.serviceWorker.getRegistrations) {
            const registrations = await navigator.serviceWorker.getRegistrations();
            registration = registrations && registrations.length ? registrations[0] : null;
        }

        if (!registration?.pushManager?.getSubscription) {
            return null;
        }

        return await registration.pushManager.getSubscription();
    } catch (error) {
        window.__pushSubscriptionError =
            error?.message ? error.message : String(error);
        console.error('Error checking push subscription:', error);
        return null;
    }
}

// Helper function to get CSRF token
function getCsrfToken() {
    return document.querySelector('input[name="csrfmiddlewaretoken"]').value || '';
} 