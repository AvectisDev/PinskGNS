from datetime import datetime

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from railway_service.models import RailwayBatch
from railway_service.tests.helpers import RailwayFixturesMixin


class RailwayBatchListFilterTests(RailwayFixturesMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.today = timezone.localdate()
        self.batch_today = self.make_batch()
        RailwayBatch.objects.filter(pk=self.batch_today.pk).update(
            begin_date=timezone.make_aware(datetime.combine(self.today, datetime.min.time())),
        )
        self.batch_old = self.make_batch()
        RailwayBatch.objects.filter(pk=self.batch_old.pk).update(
            begin_date=timezone.make_aware(datetime(2020, 1, 1, 10, 0)),
        )

    def _get_ids(self, **params):
        url = reverse('railway_service:railway_batch_list')
        response = self.client.get(url, params)
        self.assertEqual(response.status_code, 200)
        return set(response.context['page_obj'].object_list.values_list('id', flat=True))

    def test_filters_by_date_range(self):
        ids = self._get_ids(
            start_date=self.today.isoformat(),
            end_date=self.today.isoformat(),
        )
        self.assertIn(self.batch_today.id, ids)
        self.assertNotIn(self.batch_old.id, ids)

    def test_shows_all_batches_without_date_filter(self):
        ids = self._get_ids()
        self.assertEqual(ids, {self.batch_today.id, self.batch_old.id})
