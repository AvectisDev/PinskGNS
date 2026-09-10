"""Сигналы обновления кэша настроек карусели."""

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from carousel.models import CarouselSettings
from carousel.settings_cache import remove_number, upsert_from_model


@receiver(post_save, sender=CarouselSettings)
def carousel_settings_saved(sender, instance, **kwargs):
    """Публикует снимок в Redis и обновляет локальный кэш после save."""
    upsert_from_model(instance)


@receiver(post_delete, sender=CarouselSettings)
def carousel_settings_deleted(sender, instance, **kwargs):
    """Удаляет снимок из Redis и локального кэша после delete."""
    remove_number(instance.number)
