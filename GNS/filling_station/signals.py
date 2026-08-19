from django.core.cache import cache
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from filling_station.models import Balloon, BalloonsBatch, Reader


@receiver(post_save, sender=Balloon)
@receiver(post_save, sender=Reader)
@receiver(post_save, sender=BalloonsBatch)
@receiver(post_delete, sender=Balloon)
@receiver(post_delete, sender=Reader)
@receiver(post_delete, sender=BalloonsBatch)
def clear_balloon_statistic_cache(sender, **kwargs):
    cache.delete('get_balloon_statistic')
