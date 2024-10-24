"""
ASGI config for GNS project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.0/howto/deployment/asgi/
"""

import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
import GNS.filling_station.routing
from django.core.management import call_command

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'GNS.settings')

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        URLRouter(
            GNS.filling_station.routing.websocket_urlpatterns
        )
    ),
})

# Запуск команды выполнения сторонних скриптов
call_command('run_scripts')
