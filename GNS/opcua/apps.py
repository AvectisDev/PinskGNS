from django.apps import AppConfig


class OpcuaConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'opcua'
    verbose_name = 'OPC UA Bridge'
