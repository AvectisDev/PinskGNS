"""Сигналы Django для инвалидации кэша статистики баллонов и счётчиков партий."""

from django.core.cache import cache
from django.db.models import F
from django.db.models.signals import post_delete, post_save, pre_delete
from django.dispatch import receiver

from filling_station.models import Balloon, BalloonsBatch, Reader


@receiver(post_save, sender=Balloon)
@receiver(post_save, sender=Reader)
@receiver(post_save, sender=BalloonsBatch)
@receiver(post_delete, sender=Balloon)
@receiver(post_delete, sender=Reader)
@receiver(post_delete, sender=BalloonsBatch)
def clear_balloon_statistic_cache(sender, **kwargs):
    """
    Сбрасывает кэш статистики баллонов после изменения связанных моделей.

    Срабатывает на ``post_save`` и ``post_delete`` для ``Balloon``,
    ``Reader`` и ``BalloonsBatch``. Побочный эффект — удаление ключа
    ``get_balloon_statistic`` из кэша Django.

    Args:
        sender: Класс модели, отправившей сигнал.
        **kwargs: Дополнительные аргументы сигнала Django.
    """
    cache.delete('get_balloon_statistic')


@receiver(pre_delete, sender=Balloon)
def decrement_batch_rfid_count_on_balloon_delete(sender, instance, **kwargs):
    """
    Уменьшает ``amount_of_rfid`` у партий, в которые входил удаляемый баллон.

    Строка M2M снимается вместе с баллоном, а счётчик на партии хранится отдельно
    и иначе остаётся прежним.

    Args:
        sender: модель ``Balloon``.
        instance: удаляемый баллон.
        **kwargs: аргументы сигнала Django.
    """
    BalloonsBatch.objects.filter(
        balloon_list=instance,
        amount_of_rfid__gt=0,
    ).update(amount_of_rfid=F('amount_of_rfid') - 1)
