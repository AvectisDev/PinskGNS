import os
import datetime
from pathlib import Path
from dotenv import load_dotenv
from celery.schedules import crontab

load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent
LOGS_DIR = os.path.join(BASE_DIR, 'log')

SECRET_KEY = os.environ.get('SECRET_KEY')
DEBUG = os.environ.get('DEBUG')

ALLOWED_HOSTS = ['localhost', '127.0.0.1', '0.0.0.0', '10.0.2.2', '10.10.12.253', 'django']
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True

# Application definition
INSTALLED_APPS = [
    'daphne',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'core.apps.CoreConfig',
    'filling_station.apps.FillingStationConfig',
    'mobile.apps.MobileConfig',
    'carousel.apps.CarouselConfig',
    'ttn.apps.TtnConfig',
    'railway_service.apps.RailwayServiceConfig',
    'import_export',
    'rest_framework',
    'rest_framework_simplejwt',
    'crispy_forms',
    "crispy_bootstrap5",
    'debug_toolbar',
    'pghistory',
    'pgtrigger'
]

INTERNAL_IPS = [
    '127.0.0.1',
    'localhost',
    '[::1]',
]

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.BasicAuthentication',
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': datetime.timedelta(hours=8),
    'REFRESH_TOKEN_LIFETIME': datetime.timedelta(days=1),
    'ROTATE_REFRESH_TOKENS': False,
    'BLACKLIST_AFTER_ROTATION': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
}

IMPORT_EXPORT_USE_TRANSACTIONS = True

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    "debug_toolbar.middleware.DebugToolbarMiddleware",
    # 'filling_station.middleware.TimingMiddleware'
]

ROOT_URLCONF = 'GNS.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

ASGI_APPLICATION = "GNS.asgi.application"

DATABASES = {
    "default": {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': os.environ.get('DB_NAME'),
        'USER': os.environ.get('DB_USER'),
        'PASSWORD': os.environ.get('DB_PASSWORD'),
        'HOST': os.environ.get('DB_HOST'),
        'PORT': os.environ.get('DB_PORT'),
        'CONN_MAX_AGE': 600,  # Соединение будет жить 10 минут
    }
}

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': 'redis://localhost:6379/1'
    }
}

# PGHISTORY_CONTEXT_FIELD = None

# Password validation
# https://docs.djangoproject.com/en/5.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
# https://docs.djangoproject.com/en/5.0/topics/i18n/

# LANGUAGE_CODE = 'en-us'
LANGUAGE_CODE = 'ru-RU'

TIME_ZONE = 'Europe/Minsk'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.0/howto/static-files/

STATIC_URL = '/static/'
STATIC_ROOT = Path.joinpath(BASE_DIR, 'static')
STATICFILES_DIR = [
    Path.joinpath(BASE_DIR, 'filling_station/static/filling_station')
]

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# Default primary key field type
# https://docs.djangoproject.com/en/5.0/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

CELERY_BROKER_URL = 'redis://localhost:6379/0'
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_WORKER_HIJACK_ROOT_LOGGER = False
CELERY_HIJACK_ROOT_LOGGER = False
CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'
CELERY_RESULT_EXPIRES = 3600  # 1 час
CELERY_BEAT_SCHEDULE = {
    'railway_tank_processing': {
        'task': 'railway_service.tasks.railway_tank_processing',
        'schedule': 10.0,  # каждые 10 сек
    },
    'railway_batch_processing': {
        'task': 'railway_service.tasks.railway_batch_processing',
        'schedule': crontab(minute='*/20'),  # задача выполняется каждые 20 минут, начиная с 0 минут каждого часа
    },
    'auto_gas_processing': {
        'task': 'filling_station.tasks.auto_gas_processing',
        'schedule': 10.0,
    },
    'kpp_processing': {
        'task': 'filling_station.tasks.kpp_processing',
        'schedule': 60.0,
    },
}

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'style': '{',
            'format': '{asctime} - {levelname} - {module}:{lineno} - {message}',
            'datefmt': '%Y-%m-%d %H:%M:%S',
        },
        'with_msecs': {
            'format': '%(asctime)s.%(msecs)03d - %(levelname)s - %(module)s:%(lineno)d - %(message)s',
            'datefmt': '%Y-%m-%d %H:%M:%S',
        },
    },
    'handlers': {
        'filling_station_file': {
            'level': 'DEBUG',
            'class': 'logging.handlers.TimedRotatingFileHandler',
            'filename': os.path.join(LOGS_DIR, 'filling_station/filling_station.log'),
            'when': 'midnight',
            'backupCount': 30,
            'formatter': 'verbose',
            'encoding': 'utf-8',
            'delay': True,
        },
        'carousel_file': {
            'level': 'DEBUG',
            'class': 'logging.handlers.TimedRotatingFileHandler',
            'filename': os.path.join(LOGS_DIR, 'carousel/carousel.log'),
            'when': 'midnight',
            'backupCount': 30,
            'formatter': 'with_msecs',
            'encoding': 'utf-8',
            'delay': True,
        },
        'rfid_file': {
            'level': 'DEBUG',
            'class': 'logging.handlers.TimedRotatingFileHandler',
            'filename': os.path.join(LOGS_DIR, 'rfid/rfid.log'),
            'when': 'midnight',
            'backupCount': 30,
            'formatter': 'verbose',
            'encoding': 'utf-8',
            'delay': True,
        },
        'celery_file': {
            'level': 'INFO',
            'class': 'logging.handlers.TimedRotatingFileHandler',
            'filename': os.path.join(LOGS_DIR, 'celery/celery.log'),
            'when': 'midnight',
            'backupCount': 30,
            'formatter': 'verbose',
            'encoding': 'utf-8',
            'delay': True,
        },
    },
    'loggers': {
        'filling_station': {
            'handlers': ['filling_station_file'],
            'level': 'DEBUG',
            'propagate': True,
        },
        'carousel': {
            'handlers': ['carousel_file'],
            'level': 'DEBUG',
            'propagate': True,
        },
        'rfid': {
            'handlers': ['rfid_file'],
            'level': 'DEBUG',
            'propagate': True,
        },
        'celery': {
            'handlers': ['celery_file'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

DJANGO_API_HOST = 'http://localhost:8000/api'
# OPC_SERVER_URL = "opc.tcp://host.docker.internal:4841"
OPC_SERVER_URL = "opc.tcp://localhost:4841"

# Настройки почты
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = '10.11.7.1'
EMAIL_PORT = 25
EMAIL_HOST_USER = os.environ.get('GNS_EMAIL_USER')
EMAIL_HOST_PASSWORD = os.environ.get('GNS_EMAIL_PASSWORD')
DEFAULT_FROM_EMAIL = os.environ.get('GNS_DEFAULT_FROM_EMAIL')

# ITGas
MIRIADA_API_POST_URL = os.environ.get('MIRIADA_API_POST_URL')
MIRIADA_AUTH_LOGIN = os.environ.get('MIRIADA_AUTH_LOGIN')
MIRIADA_AUTH_PASSWORD = os.environ.get('MIRIADA_AUTH_PASSWORD')

GAS_TYPE_CHOICES = [
    ('Не выбран', 'Не выбран'),
    ('СПБТ', 'СПБТ'),
    ('ПБА', 'ПБА'),
]
