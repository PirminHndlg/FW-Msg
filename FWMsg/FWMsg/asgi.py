"""
ASGI config for FWMsg project.

Handles both standard HTTP traffic (via Django) and WebSocket connections
(via Django Channels). The WebSocket URL namespace is /ws/chat/...

IMPORTANT: get_asgi_application() must be called before any import that
touches Django models or the app registry (e.g. chat.routing → chat.consumers
→ chat.models). It calls django.setup() internally.
"""

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "FWMsg.settings")

from django.core.asgi import get_asgi_application

# Initialize Django (calls django.setup()) before any app-level imports.
django_asgi_app = get_asgi_application()

from channels.auth import AuthMiddlewareStack       # noqa: E402
from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402
import chat.routing                                  # noqa: E402

application = ProtocolTypeRouter(
    {
        # All normal HTTP requests are handled by Django as before.
        "http": django_asgi_app,
        # WebSocket connections go through Channels.
        # AuthMiddlewareStack reads the session cookie and populates
        # scope["user"] exactly like request.user in views.
        "websocket": AuthMiddlewareStack(
            URLRouter(chat.routing.websocket_urlpatterns)
        ),
    }
)
