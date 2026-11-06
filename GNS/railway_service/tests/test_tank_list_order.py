from datetime import datetime

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from railway_service.tests.helpers import RailwayFixturesMixin


class RailwayTankListOrderTests(RailwayFixturesMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.older = self.make_tank(
            11100001,
            arrival_at=timezone.make_aware(datetime(2025, 1, 1, 10, 0)),
        )
        self.newer = self.make_tank(
            11100002,
            arrival_at=timezone.make_aware(datetime(2026, 6, 1, 12, 0)),
        )
        self.no_history = self.make_tank(11100003)

    def test_list_ordered_by_latest_arrival_desc(self):
        response = self.client.get(reverse('railway_service:railway_tank_list'))
        self.assertEqual(response.status_code, 200)
        ids = [tank.pk for tank in response.context['page_obj'].object_list]
        self.assertEqual(ids[:2], [self.newer.pk, self.older.pk])
        self.assertGreater(ids.index(self.no_history.pk), ids.index(self.older.pk))
