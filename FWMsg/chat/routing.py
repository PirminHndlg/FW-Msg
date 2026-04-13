from django.urls import re_path

from . import consumers

websocket_urlpatterns = [
    re_path(r"ws/chat/badge/$", consumers.ChatBadgeConsumer.as_asgi()),
    # Handles both direct and group chats.
    # chat_type: "direct" | "group"
    # identifier: the hash identifier of the chat object
    re_path(
        r"ws/chat/(?P<chat_type>direct|group)/(?P<identifier>[^/]+)/$",
        consumers.ChatConsumer.as_asgi(),
    ),
]
