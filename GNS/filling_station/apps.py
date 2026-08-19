from django.apps import AppConfig


class FillingStationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'filling_station'
    verbose_name = "Газонаполнительная станция"

    def ready(self):
        from filling_station import signals  # noqa: F401
