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
        if ("serviceWorker" in navigator) {
            try {
                const swRegistration = await navigator.serviceWorker.register("/service-worker.js");
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
                message: 'Berechtigung für Benachrichtigungen verweigert. Bitte erlauben Sie Benachrichtigungen in Ihren Browser-Einstellungen.'
            };
        }

        // Wait for the service worker to be ready
        // const applicationServerKey = convertDataURIToBinary(publicKey)
        const applicationServerKey = urlBase64ToUint8Array(publicKey);

        // Get existing subscription
        const setUpPushPermission = async () => {
            const registration = await navigator.serviceWorker.ready
            const subscription = await registration.pushManager.subscribe({
              userVisibleOnly: true,
              applicationServerKey: applicationServerKey,
            })
            return subscription
          }
          
        const subscription = await setUpPushPermission()

        // Send the subscription to the server
        const response = await fetch('/push/save-subscription/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken()
            },
            body: JSON.stringify(subscription)
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.message || 'Failed to save subscription');
        }
        
        return {
            success: true,
            message: 'Sie haben sich erfolgreich für Push-Benachrichtigungen angemeldet.'
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

    try {
        const registration = await navigator.serviceWorker.getRegistration();
        if (!registration) {
            return null;
        }
        
        const subscription = await registration.pushManager.getSubscription();
        return subscription;
    } catch (error) {
        console.error('Error checking push subscription:', error);
        return null;
    }
}

// Helper function to get CSRF token
function getCsrfToken() {
    return document.querySelector('input[name="csrfmiddlewaretoken"]').value || '';
} 