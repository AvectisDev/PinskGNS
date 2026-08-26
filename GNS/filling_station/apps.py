"""Конфигурация приложения filling_station (газонаполнительная станция)."""

from django.apps import AppConfig


class FillingStationConfig(AppConfig):
    """Конфиг приложения ГНС: подключает сигналы при старте Django."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'filling_station'
    verbose_name = "Газонаполнительная станция"

    def ready(self):
        """
        Импортирует сигналы приложения после загрузки моделей.

        Вызывается Django один раз при инициализации приложения.
        Побочный эффект — регистрация обработчиков из ``signals``.
        """
        from filling_station import signals  # noqa: F401
