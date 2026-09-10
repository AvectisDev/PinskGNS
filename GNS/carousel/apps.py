from django.apps import AppConfig


class CarouselConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'carousel'
    verbose_name = "Карусель наполнения баллонов"

    def ready(self):
        # Регистрация post_save/post_delete для кэша CarouselSettings.
        from . import signals  # noqa: F401
