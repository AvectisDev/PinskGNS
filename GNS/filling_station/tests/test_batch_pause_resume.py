"""Edge-кейсы pause/resume партий."""

from unittest.mock import patch

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from filling_station.models import BatchStatus
from filling_station.services.batches import (
    add_balloon_to_batch_by_nfc,
    pause_balloons_batch,
    resume_balloons_batch,
)
from filling_station.tests.factories import (
    make_balloon,
    make_batch,
    make_reader,
    make_truck,
    make_user,
)


class BatchPauseResumeEdgeTests(APITestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_authenticate(self.user)
        self.truck = make_truck(registration_number='AC 5512-1')
        make_reader(6, function='l')
        self.batch = make_batch(
            batch_type='l',
            truck=self.truck,
            reader_number=6,
            amount_of_ttn=5,
            user=self.user,
        )
        self.balloon = make_balloon(nfc_tag='pauseres01e0')

    def test_pause_rejects_non_active(self):
        pause_balloons_batch(self.batch)
        ok, message = pause_balloons_batch(self.batch)
        self.assertFalse(ok)
        self.assertIn('не в работе', message)

        url = reverse('filling_station_api:balloons-loading-pause', args=[self.batch.id])
        response = self.client.post(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_resume_rejects_non_paused(self):
        ok, message = resume_balloons_batch(self.batch)
        self.assertFalse(ok)
        self.assertIn('не приостановлена', message)

        url = reverse('filling_station_api:balloons-loading-resume', args=[self.batch.id])
        response = self.client.post(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_resume_pauses_other_active_on_same_reader(self):
        pause_balloons_batch(self.batch)
        other = make_batch(
            batch_type='l',
            truck=self.truck,
            reader_number=6,
            ttn_id=99901,
            amount_of_ttn=2,
            status=BatchStatus.ACTIVE,
            user=self.user,
        )
        ok, _ = resume_balloons_batch(self.batch)
        self.assertTrue(ok)
        self.batch.refresh_from_db()
        other.refresh_from_db()
        self.assertEqual(self.batch.status, BatchStatus.ACTIVE)
        self.assertEqual(other.status, BatchStatus.PAUSED)

    @patch('filling_station.services.batches.post_status_to_miriada')
    def test_after_resume_add_sends_same_number_auto(self, mock_post):
        # Для loading reader 6 payload без number_auto; используем unloading reader 4
        truck = make_truck(registration_number='AP 1852-1')
        make_reader(4, function='u')
        batch = make_batch(
            batch_type='u',
            truck=truck,
            reader_number=4,
            amount_of_ttn=5,
            ttn_id=57097,
            user=self.user,
        )
        balloon = make_balloon(nfc_tag='pauseres02e0')
        pause_balloons_batch(batch)
        resume_balloons_batch(batch)
        add_balloon_to_batch_by_nfc(batch, balloon.nfc_tag)
        mock_post.assert_called_once()
        _url, payload, send_type = mock_post.call_args[0][:3]
        self.assertEqual(send_type, 'loading_into_truck')
        self.assertEqual(payload['number_auto'], 'AP 1852-1')
        self.assertEqual(payload['id_ttn'], 57097)
