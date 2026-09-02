"""
Точка входа subprocess listener карусели.

Запускается из asgi.py или management command carousel_process
как ``python -m carousel.management.commands.carousel.main``.
"""

import logging.config
import os

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'GNS.settings')
django.setup()

logging.config.dictConfig(django.conf.settings.LOGGING)

from carousel.listener.runner import main  # noqa: E402

if __name__ == '__main__':
    main()
