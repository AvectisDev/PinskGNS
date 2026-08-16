from unittest.mock import patch

from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from filling_station.exceptions import MiriadaAPIError
from filling_station.models import Balloon, BalloonsBatch, ReaderSettings, Truck, TruckType
from filling_station.services import (
    add_balloon_to_batch_by_nfc,
    processing_request_without_nfc,
    save_and_close_balloons_batch,
    should_send_balloon_status_immediately,
)


class BalloonsBatchCloseTests(APITestCase):
    def setUp(self):
        try:
            self.user = User.objects.get(pk=1)
        except User.DoesNotExist:
            self.user = User.objects.create_user(id=1, username='batch_operator', password='x')
        self.client.force_authenticate(self.user)

        self.truck_type = TruckType.objects.create(type='Трал')
        self.truck = Truck.objects.create(
            registration_number='2222BB-1',
            type=self.truck_type,
            car_brand='МАЗ',
        )
        self.reader = ReaderSettings.objects.create(
            number=6,
            ip='10.10.2.26',
            status='empty',
            function='l',
        )
        self.balloon = Balloon.objects.create(nfc_tag='aabbccdde0')
        self.batch = BalloonsBatch.objects.create(
            batch_type='l',
            truck=self.truck,
            reader_number=6,
            ttn_id=14769,
            amount_of_ttn=1,
            is_active=True,
            balloons_type='e',
            user=self.user,
        )

    def test_create_requires_amount_of_ttn(self):
        url = reverse('filling_station_api:balloons-loading-list')
        response = self.client.post(
            url,
            {
                'truck': self.truck.id,
                'reader_number': 6,
                'ttn_id': 14770,
                'balloons_type': 'e',
                'is_active': True,
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('amount_of_ttn', response.data)

    def test_create_saves_amount_of_ttn(self):
        url = reverse('filling_station_api:balloons-loading-list')
        response = self.client.post(
            url,
            {
                'truck': self.truck.id,
                'reader_number': 6,
                'ttn_id': 14770,
                'amount_of_ttn': 12,
                'balloons_type': 'e',
                'is_active': True,
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['amount_of_ttn'], 12)

    def test_rfid_amount_returns_three_counters(self):
        self.batch.amount_of_rfid = 4
        self.batch.amount_of_sensor = 5
        self.batch.save(update_fields=['amount_of_rfid', 'amount_of_sensor'])
        url = reverse('filling_station_api:balloons-loading-rfid-amount', args=[self.batch.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['amount_of_ttn'], 1)
        self.assertEqual(response.data['amount_of_rfid'], 4)
        self.assertEqual(response.data['amount_of_sensor'], 5)

    @patch('filling_station.services.batches.send_status_to_miriada')
    def test_add_balloon_does_not_send_to_miriada(self, mock_send):
        result = add_balloon_to_batch_by_nfc(self.batch, self.balloon.nfc_tag)
        self.assertTrue(result['success'])
        mock_send.assert_not_called()
        self.batch.refresh_from_db()
        self.assertEqual(self.batch.amount_of_rfid, 1)
        self.assertTrue(self.batch.balloon_list.filter(nfc_tag=self.balloon.nfc_tag).exists())

    def test_sensor_increments_active_batch(self):
        reader = processing_request_without_nfc(6)
        self.assertIsNotNone(reader)
        self.assertEqual(reader.number, 6)
        self.batch.refresh_from_db()
        self.assertEqual(self.batch.amount_of_sensor, 1)

    def test_defer_status_when_batch_is_active(self):
        self.assertFalse(should_send_balloon_status_immediately(6))
        self.assertTrue(should_send_balloon_status_immediately(8))

    def test_send_immediately_when_no_active_batch(self):
        self.batch.is_active = False
        self.batch.save(update_fields=['is_active'])
        self.assertTrue(should_send_balloon_status_immediately(6))

    @patch('ttn.services.close_ttn_in_miriada')
    @patch('filling_station.services.batches.send_status_to_miriada')
    def test_close_sends_balloons_then_closes_ttn(self, mock_send, mock_close):
        mock_close.return_value = (True, None)
        self.batch.add_balloon(self.balloon.nfc_tag)

        success, error, data = save_and_close_balloons_batch(self.batch)
        self.assertTrue(success)
        self.assertIsNone(error)
        mock_send.assert_called_once()
        self.assertEqual(mock_send.call_args.kwargs['reader'], 6)
        self.assertEqual(mock_send.call_args.kwargs['nfc_tag'], self.balloon.nfc_tag)
        self.assertEqual(mock_send.call_args.kwargs['batch'].pk, self.batch.pk)
        mock_close.assert_called_once()
        self.batch.refresh_from_db()
        self.assertFalse(self.batch.is_active)
        self.assertTrue(self.batch.miriada_balloons_sent)
        self.assertEqual(data['amount_of_ttn'], 1)

    @patch('ttn.services.close_ttn_in_miriada')
    @patch('filling_station.services.batches.send_status_to_miriada')
    def test_close_rejected_when_rfid_does_not_match_ttn(self, mock_send, mock_close):
        success, error, data = save_and_close_balloons_batch(self.batch)
        self.assertFalse(success)
        self.assertTrue(error['count_mismatch'])
        self.assertIsNone(data)
        mock_send.assert_not_called()
        mock_close.assert_not_called()
        self.batch.refresh_from_db()
        self.assertTrue(self.batch.is_active)

    @patch('ttn.services.close_ttn_in_miriada')
    @patch('filling_station.services.batches.send_status_to_miriada')
    def test_close_stops_if_balloon_status_fails(self, mock_send, mock_close):
        mock_send.side_effect = MiriadaAPIError('miriada down')
        self.batch.add_balloon(self.balloon.nfc_tag)

        success, error, data = save_and_close_balloons_batch(self.batch)
        self.assertFalse(success)
        self.assertTrue(error['miriada_close_failed'])
        mock_close.assert_not_called()
        self.batch.refresh_from_db()
        self.assertTrue(self.batch.is_active)
        self.assertFalse(self.batch.miriada_balloons_sent)

    @patch('ttn.services.close_ttn_in_miriada')
    @patch('filling_station.services.batches.send_status_to_miriada')
    def test_retry_does_not_resend_balloons(self, mock_send, mock_close):
        mock_close.return_value = (True, None)
        self.batch.add_balloon(self.balloon.nfc_tag)
        self.batch.miriada_balloons_sent = True
        self.batch.miriada_close_failed = True
        self.batch.save(update_fields=['miriada_balloons_sent', 'miriada_close_failed'])

        success, error, _data = save_and_close_balloons_batch(self.batch)
        self.assertTrue(success)
        self.assertIsNone(error)
        mock_send.assert_not_called()
        mock_close.assert_called_once()

    def test_http_close_returns_400_on_count_mismatch(self):
        url = reverse('filling_station_api:balloons-loading-detail', args=[self.batch.id])
        response = self.client.patch(url, {'is_active': False}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(response.data['count_mismatch'])
        self.batch.refresh_from_db()
        self.assertTrue(self.batch.is_active)

    @patch('ttn.services.close_ttn_in_miriada')
    @patch('filling_station.services.batches.send_status_to_miriada')
    def test_http_close_returns_502_when_miriada_fails_after_statuses(self, mock_send, mock_close):
        mock_send.side_effect = MiriadaAPIError('miriada down')
        self.batch.add_balloon(self.balloon.nfc_tag)
        url = reverse('filling_station_api:balloons-loading-detail', args=[self.batch.id])
        response = self.client.patch(url, {'is_active': False}, format='json')
        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)
        self.assertTrue(response.data['miriada_close_failed'])
        mock_close.assert_not_called()
        self.batch.refresh_from_db()
        self.assertTrue(self.batch.is_active)
        self.assertFalse(self.batch.miriada_balloons_sent)
