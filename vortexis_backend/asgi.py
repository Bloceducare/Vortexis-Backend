"""
ASGI config for vortexis_backend project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.1/howto/deployment/asgi/
"""

import os
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from django.core.asgi import get_asgi_application
from django.urls import path

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'vortexis_backend.settings')

django_asgi_app = get_asgi_application()

from communications.consumers import ConversationConsumer  # noqa: E402
from communications.auth import JWTAuthMiddlewareStack  # noqa: E402

websocket_urlpatterns = [
    path('ws/communications/conversations/<int:conversation_id>/', ConversationConsumer.as_asgi()),
]

application = ProtocolTypeRouter({
    'http': django_asgi_app,
    'websocket': JWTAuthMiddlewareStack(
        URLRouter(websocket_urlpatterns)
    ),
})
