from django.urls import path
from GNS.filling_station import consumers

websocket_urlpatterns = [
    path('ws/some_path/', consumers.YourConsumer.as_asgi()),
]