/*
 * Service Worker for Web Push Notifications
 * This file handles incoming push notifications and displays them to the user.
 */

self.addEventListener('push', function(event) {
    console.log('[Service Worker] Push Received.');
    
    // Parse the data from the push event
    let data = {};
    if (event.data) {
        try {
            data = event.data.json();
        } catch (e) {
            console.error('Error parsing push data:', e);
            data = {
                title: 'Neue Benachrichtigung',
                body: event.data.text()
            };
        }
    }
    
    // Default notification options
    const title = data.title || 'Neue Benachrichtigung';
    const options = {
        body: data.body || 'Du hast eine neue Benachrichtigung erhalten.',
        icon: data.icon || '/static/img/logo.png',
        badge: '/static/img/badge.png',
        data: {
            url: data.url || '/'
        },
        // Show notification even if the app is in the foreground
        requireInteraction: data.requireInteraction || false,
        // Group notifications with the same tag
        tag: data.tag
    };
    
    // Show the notification to the user
    event.waitUntil(
        self.registration.showNotification(title, options)
    );
});

// Handle notification click
self.addEventListener('notificationclick', function(event) {
    console.log('[Service Worker] Notification click received.');
    
    // Close the notification
    event.notification.close();
    
    // Get URL from the notification data
    let url = '/';
    if (event.notification.data && event.notification.data.url) {
        url = event.notification.data.url;
    }
    
    // Open the URL when the user clicks the notification
    event.waitUntil(
        clients.openWindow(url)
    );
});

// Installation and activation handling
self.addEventListener('install', event => {
    console.log('[Service Worker] Installing Service Worker');
    self.skipWaiting();
});

self.addEventListener('activate', event => {
    console.log('[Service Worker] Activating Service Worker');
    return self.clients.claim();
}); 