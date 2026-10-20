"""Сигналы инвалидации кэша статистики."""

from django.core.cache import cache
from django.test import TestCase

from filling_station.tests.factories import make_balloon, make_batch, make_truck, make_user


class ClearBalloonStatisticCacheTests(TestCase):
    def test_balloon_save_clears_cache(self):
        cache.set('get_balloon_statistic', [{'x': 1}], 600)
        make_balloon(nfc_tag='sigcache01e0')
        self.assertIsNone(cache.get('get_balloon_statistic'))

    def test_batch_save_clears_cache(self):
        cache.set('get_balloon_statistic', [{'x': 1}], 600)
        make_batch(truck=make_truck(), user=make_user())
        self.assertIsNone(cache.get('get_balloon_statistic'))

    def test_balloon_delete_clears_cache(self):
        balloon = make_balloon(nfc_tag='sigcache02e0')
        cache.set('get_balloon_statistic', [{'x': 1}], 600)
        balloon.delete()
        self.assertIsNone(cache.get('get_balloon_statistic'))
