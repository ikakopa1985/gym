import os

from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application
from channels.auth import AuthMiddlewareStack

import gymapp.routing

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "gym.settings")

django_asgi_app = get_asgi_application()

application = ProtocolTypeRouter({
    "http": django_asgi_app,

    "websocket": AuthMiddlewareStack(
        URLRouter(
            gymapp.routing.websocket_urlpatterns
        )
    ),
})