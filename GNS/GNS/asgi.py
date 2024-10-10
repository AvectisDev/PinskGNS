"""
ASGI config for GNS project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.0/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application
from django.core.management import call_command

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'GNS.settings')

application = get_asgi_application()

# Запуск команды выполнения сторонних скриптов
call_command('run_scripts')
