from unittest.mock import patch

from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from filling_station.exceptions import MiriadaAPIError
from filling_station.models import Balloon, BalloonsBatch, BatchStatus, ReaderSettings, Truck, TruckType
from filling_station.api.batch_status import STATUS_TO_API
from filling_station.services import (
    add_balloon_to_batch_by_nfc,
    pause_balloons_batch,
    processing_request_without_nfc,
    resume_balloons_batch,
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
            status=BatchStatus.ACTIVE,
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
                'status': STATUS_TO_API[BatchStatus.ACTIVE],
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
                'status': STATUS_TO_API[BatchStatus.ACTIVE],
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['amount_of_ttn'], 12)
        self.assertEqual(response.data['status'], STATUS_TO_API[BatchStatus.ACTIVE])

    def test_create_pauses_previous_active_batch_on_same_reader(self):
        url = reverse('filling_station_api:balloons-loading-list')
        response = self.client.post(
            url,
            {
                'truck': self.truck.id,
                'reader_number': 6,
                'ttn_id': 14771,
                'amount_of_ttn': 5,
                'balloons_type': 'e',
                'status': STATUS_TO_API[BatchStatus.ACTIVE],
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.batch.refresh_from_db()
        self.assertEqual(self.batch.status, BatchStatus.PAUSED)

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

    @patch('filling_station.services.batches.post_status_to_miriada')
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

    def test_sensor_ignored_for_paused_batch(self):
        pause_balloons_batch(self.batch)
        processing_request_without_nfc(6)
        self.batch.refresh_from_db()
        self.assertEqual(self.batch.amount_of_sensor, 0)

    def test_defer_status_when_batch_is_active(self):
        self.assertFalse(should_send_balloon_status_immediately(6))
        self.assertTrue(should_send_balloon_status_immediately(8))

    def test_send_immediately_only_for_filling_reader(self):
        self.batch.status = BatchStatus.PAUSED
        self.batch.save(update_fields=['status'])
        self.assertFalse(should_send_balloon_status_immediately(6))
        self.assertFalse(should_send_balloon_status_immediately(3))
        self.assertTrue(should_send_balloon_status_immediately(8))

    @patch('ttn.services.close_ttn_in_miriada')
    @patch('filling_station.services.batches.post_status_to_miriada')
    def test_close_sends_balloons_then_closes_ttn(self, mock_send, mock_close):
        mock_close.return_value = (True, None)
        self.batch.add_balloon(self.balloon.nfc_tag)

        success, error, data = save_and_close_balloons_batch(self.batch)
        self.assertTrue(success)
        self.assertIsNone(error)
        mock_send.assert_called_once()
        self.assertEqual(mock_send.call_args.args[1]['nfctag'], self.balloon.nfc_tag)
        self.assertEqual(mock_send.call_args.args[2], 'registering_in_warehouse')
        mock_close.assert_called_once()
        self.batch.refresh_from_db()
        self.assertEqual(self.batch.status, BatchStatus.COMPLETED)
        self.assertTrue(self.batch.miriada_balloons_sent)
        self.assertEqual(data['amount_of_ttn'], 1)

    @patch('ttn.services.close_ttn_in_miriada')
    @patch('filling_station.services.batches.post_status_to_miriada')
    def test_close_rejected_when_rfid_does_not_match_ttn(self, mock_send, mock_close):
        success, error, data = save_and_close_balloons_batch(self.batch)
        self.assertFalse(success)
        self.assertTrue(error['count_mismatch'])
        self.assertIsNone(data)
        mock_send.assert_not_called()
        mock_close.assert_not_called()
        self.batch.refresh_from_db()
        self.assertEqual(self.batch.status, BatchStatus.ACTIVE)

    @patch('ttn.services.close_ttn_in_miriada')
    @patch('filling_station.services.batches.post_status_to_miriada')
    def test_close_stops_if_balloon_status_fails(self, mock_send, mock_close):
        mock_send.side_effect = MiriadaAPIError('miriada down')
        self.batch.add_balloon(self.balloon.nfc_tag)

        success, error, data = save_and_close_balloons_batch(self.batch)
        self.assertFalse(success)
        self.assertTrue(error['miriada_close_failed'])
        mock_close.assert_not_called()
        self.batch.refresh_from_db()
        self.assertEqual(self.batch.status, BatchStatus.MIRIADA_ERROR)
        self.assertFalse(self.batch.miriada_balloons_sent)

    @patch('ttn.services.close_ttn_in_miriada')
    @patch('filling_station.services.batches.post_status_to_miriada')
    def test_retry_does_not_resend_balloons(self, mock_send, mock_close):
        mock_close.return_value = (True, None)
        self.batch.add_balloon(self.balloon.nfc_tag)
        self.batch.miriada_balloons_sent = True
        self.batch.status = BatchStatus.MIRIADA_ERROR
        self.batch.save(update_fields=['miriada_balloons_sent', 'status', 'miriada_close_failed'])

        success, error, _data = save_and_close_balloons_batch(self.batch)
        self.assertTrue(success)
        self.assertIsNone(error)
        mock_send.assert_not_called()
        mock_close.assert_called_once()

    @patch('ttn.services.close_ttn_in_miriada')
    @patch('filling_station.services.batches.post_status_to_miriada')
    def test_close_sends_all_balloon_statuses(self, mock_send, mock_close):
        mock_close.return_value = (True, None)
        extra = [
            Balloon.objects.create(nfc_tag='bbccddeeffe0'),
            Balloon.objects.create(nfc_tag='ccddeeff00e0'),
        ]
        self.batch.add_balloon(self.balloon.nfc_tag)
        for balloon in extra:
            self.batch.add_balloon(balloon.nfc_tag)
        self.batch.amount_of_ttn = 3
        self.batch.save(update_fields=['amount_of_ttn'])

        success, error, _data = save_and_close_balloons_batch(self.batch)
        self.assertTrue(success)
        self.assertIsNone(error)
        self.assertEqual(mock_send.call_count, 3)
        sent_tags = {call.args[1]['nfctag'] for call in mock_send.call_args_list}
        self.assertEqual(
            sent_tags,
            {self.balloon.nfc_tag, extra[0].nfc_tag, extra[1].nfc_tag},
        )

    def test_http_close_returns_400_on_count_mismatch(self):
        url = reverse('filling_station_api:balloons-loading-detail', args=[self.batch.id])
        response = self.client.patch(url, {'status': STATUS_TO_API[BatchStatus.COMPLETED]}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(response.data['count_mismatch'])
        self.batch.refresh_from_db()
        self.assertEqual(self.batch.status, BatchStatus.ACTIVE)

    @patch('ttn.services.close_ttn_in_miriada')
    @patch('filling_station.services.batches.post_status_to_miriada')
    def test_http_close_returns_502_when_miriada_fails_after_statuses(self, mock_send, mock_close):
        mock_send.side_effect = MiriadaAPIError('miriada down')
        self.batch.add_balloon(self.balloon.nfc_tag)
        url = reverse('filling_station_api:balloons-loading-detail', args=[self.batch.id])
        response = self.client.patch(url, {'status': STATUS_TO_API[BatchStatus.COMPLETED]}, format='json')
        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)
        self.assertTrue(response.data['miriada_close_failed'])
        self.assertEqual(response.data['status'], STATUS_TO_API[BatchStatus.MIRIADA_ERROR])
        mock_close.assert_not_called()
        self.batch.refresh_from_db()
        self.assertEqual(self.batch.status, BatchStatus.MIRIADA_ERROR)
        self.assertFalse(self.batch.miriada_balloons_sent)

    def test_pause_and_resume_batch(self):
        url_pause = reverse('filling_station_api:balloons-loading-pause', args=[self.batch.id])
        response = self.client.post(url_pause, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.batch.refresh_from_db()
        self.assertEqual(self.batch.status, BatchStatus.PAUSED)

        url_resume = reverse('filling_station_api:balloons-loading-resume', args=[self.batch.id])
        response = self.client.post(url_resume, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.batch.refresh_from_db()
        self.assertEqual(self.batch.status, BatchStatus.ACTIVE)

    def test_amount_without_rfid_is_sum_of_liter_fields(self):
        self.batch.amount_of_sensor = 147
        self.batch.amount_of_rfid = 147
        self.batch.amount_of_5_liters = 1
        self.batch.amount_of_12_liters = 2
        self.batch.amount_of_27_liters = 3
        self.batch.amount_of_50_liters = 4
        self.batch.save()
        self.assertEqual(self.batch.get_amount_without_rfid(), 10)

    def test_api_add_balloon_logs_action(self):
        url = reverse('filling_station_api:balloons-loading-add-balloon', args=[self.batch.id])
        with self.assertLogs('filling_station', level='INFO') as logs:
            response = self.client.patch(url, {'nfc': self.balloon.nfc_tag}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(
            any('API add-balloon' in line and self.balloon.nfc_tag in line for line in logs.output)
        )

    def test_api_add_balloon_rejected_for_completed_batch(self):
        self.batch.status = BatchStatus.COMPLETED
        self.batch.save(update_fields=['status'])
        url = reverse('filling_station_api:balloons-loading-add-balloon', args=[self.batch.id])
        response = self.client.patch(url, {'nfc': self.balloon.nfc_tag}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
