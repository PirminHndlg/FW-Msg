"""
ASGI config for FWMsg project.

Handles both standard HTTP traffic (via Django) and WebSocket connections
(via Django Channels). The WebSocket URL namespace is /ws/chat/...
"""

import os

from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "FWMsg.settings")

# Import chat routing after setting the env var so Django is configured first.
import chat.routing  # noqa: E402

application = ProtocolTypeRouter(
    {
        # All normal HTTP requests are handled by Django as before.
        "http": get_asgi_application(),
        # WebSocket connections go through Channels.
        # AuthMiddlewareStack reads the session cookie and populates
        # scope["user"] exactly like request.user in views.
        "websocket": AuthMiddlewareStack(
            URLRouter(chat.routing.websocket_urlpatterns)
        ),
    }
)
