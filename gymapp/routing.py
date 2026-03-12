from django.urls import re_path
from .consumers import CardConsumer

websocket_urlpatterns = [
    re_path(r"ws/cards/$", CardConsumer.as_asgi()),
]