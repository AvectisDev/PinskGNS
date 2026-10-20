"""API is-active / last-active / rfid-amount."""

from datetime import timedelta
from unittest.mock import patch

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from filling_station.exceptions import MiriadaAPIError
from filling_station.models import BalloonsBatch, BatchStatus
from filling_station.services.batches import add_balloon_to_batch_by_nfc
from filling_station.tests.factories import (
    make_balloon,
    make_batch,
    make_reader,
    make_truck,
    make_user,
)


class BatchStatusApiTests(APITestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_authenticate(self.user)
        self.truck = make_truck()
        make_reader(6, function='l')
        self.batch = make_batch(
            batch_type='l',
            truck=self.truck,
            reader_number=6,
            amount_of_ttn=3,
            user=self.user,
        )

    def test_active_returns_open_batches(self):
        make_batch(
            batch_type='l',
            truck=self.truck,
            reader_number=6,
            ttn_id=200,
            status=BatchStatus.PAUSED,
            user=self.user,
        )
        make_batch(
            batch_type='l',
            truck=self.truck,
            reader_number=6,
            ttn_id=201,
            status=BatchStatus.COMPLETED,
            user=self.user,
        )
        response = self.client.get('/api/balloons-loading/active/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = {item['id'] for item in response.data}
        self.assertIn(self.batch.id, ids)
        # COMPLETED не в OPEN_BATCH_STATUSES
        completed = [b for b in response.data if b.get('status') == 3]
        self.assertEqual(completed, [])

    def test_active_excludes_batches_older_than_5_days(self):
        old = make_batch(
            batch_type='l',
            truck=self.truck,
            reader_number=6,
            ttn_id=300,
            status=BatchStatus.PAUSED,
            user=self.user,
        )
        # auto_now_add не даёт задать started_at при create — правим напрямую
        BalloonsBatch.objects.filter(pk=old.pk).update(
            started_at=timezone.now() - timedelta(days=6),
        )
        response = self.client.get('/api/balloons-loading/active/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [item['id'] for item in response.data]
        self.assertNotIn(old.id, ids)
        self.assertIn(self.batch.id, ids)

    def test_active_ordered_newest_first(self):
        older = make_batch(
            batch_type='l',
            truck=self.truck,
            reader_number=6,
            ttn_id=301,
            status=BatchStatus.PAUSED,
            user=self.user,
        )
        newer = make_batch(
            batch_type='l',
            truck=self.truck,
            reader_number=6,
            ttn_id=302,
            status=BatchStatus.PAUSED,
            user=self.user,
        )
        BalloonsBatch.objects.filter(pk=older.pk).update(
            started_at=timezone.now() - timedelta(days=2),
        )
        BalloonsBatch.objects.filter(pk=newer.pk).update(
            started_at=timezone.now() - timedelta(hours=1),
        )
        BalloonsBatch.objects.filter(pk=self.batch.pk).update(
            started_at=timezone.now() - timedelta(days=1),
        )
        response = self.client.get('/api/balloons-loading/active/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [item['id'] for item in response.data]
        self.assertEqual(ids[:3], [newer.id, self.batch.id, older.id])

    def test_last_active_404_when_none(self):
        self.batch.status = BatchStatus.PAUSED
        self.batch.save(update_fields=['status'])
        response = self.client.get('/api/balloons-loading/last-active/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_last_active_returns_active_batch(self):
        response = self.client.get('/api/balloons-loading/last-active/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], self.batch.id)

    @patch('filling_station.services.batches.post_status_to_miriada')
    def test_rfid_amount_includes_error_balloons(self, mock_post):
        mock_post.side_effect = MiriadaAPIError('Автомобиль не найден')
        balloon = make_balloon(nfc_tag='errball001e0')
        add_balloon_to_batch_by_nfc(self.batch, balloon.nfc_tag)
        url = reverse(
            'filling_station_api:balloons-loading-rfid-amount',
            args=[self.batch.id],
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['amount_of_rfid'], 1)
        errors = response.data.get('error_balloons') or []
        self.assertTrue(any(e.get('nfc_tag') == balloon.nfc_tag for e in errors))
