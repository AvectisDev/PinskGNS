import os
import django
from celery import Celery
import logging.config
from django.conf import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'GNS.settings')

django.setup()

# Применяем настройки логирования Django
logging.config.dictConfig(settings.LOGGING)

app = Celery('GNS')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
