from unittest.mock import patch

from django.contrib.auth.models import User
from django.urls import NoReverseMatch, reverse
from rest_framework import status
from rest_framework.test import APITestCase

from filling_station.exceptions import MiriadaAPIError
from filling_station.models import Balloon, BalloonsBatch, BatchStatus, ReaderSettings
from transport.models import Truck, TruckType
from filling_station.api.balloon_batches import _balloon_operation_error_status
from filling_station.api.batch_status import STATUS_TO_API
from filling_station.services.batches import (
    add_balloon_to_batch_by_nfc,
    pause_balloons_batch,
    save_and_close_balloons_batch,
    should_send_balloon_status_immediately,
)
from filling_station.services.rfid import processing_request_without_nfc


class BalloonsBatchCloseTests(APITestCase):
    def setUp(self):
        try:
            self.user = User.objects.get(pk=1)
        except User.DoesNotExist:
            self.user = User.objects.create_user(id=1, username='batch_operator', password='x')
        self.client.force_authenticate(self.user)

        self.truck_type = TruckType.objects.create(type='Трал')
        self.truck = Truck.objects.create(
            registration_number='BB 2222-1',
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
        extras = [
            Balloon.objects.create(nfc_tag='rfidcnt0001e0'),
            Balloon.objects.create(nfc_tag='rfidcnt0002e0'),
            Balloon.objects.create(nfc_tag='rfidcnt0003e0'),
        ]
        with patch('filling_station.services.batches.post_status_to_miriada'):
            self.batch.add_balloon(self.balloon.nfc_tag)
            for balloon in extras:
                self.batch.add_balloon(balloon.nfc_tag)
        self.batch.amount_of_sensor = 5
        self.batch.save(update_fields=['amount_of_sensor'])
        url = reverse('filling_station_api:balloons-loading-rfid-amount', args=[self.batch.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['amount_of_ttn'], 1)
        self.assertEqual(response.data['amount_of_rfid'], 4)
        self.assertEqual(response.data['amount_of_sensor'], 5)

    @patch('filling_station.services.batches.post_status_to_miriada')
    def test_add_balloon_sends_status_to_miriada(self, mock_send):
        result = add_balloon_to_batch_by_nfc(self.batch, self.balloon.nfc_tag)
        self.assertTrue(result['success'])
        mock_send.assert_called_once()
        self.assertEqual(mock_send.call_args.args[2], 'registering_in_warehouse')
        self.assertEqual(mock_send.call_args.args[1]['nfctag'], self.balloon.nfc_tag)
        self.batch.refresh_from_db()
        self.balloon.refresh_from_db()
        self.assertEqual(self.batch.rfid_balloon_count(), 1)
        self.assertEqual(self.balloon.miriada_status_error, '')
        self.assertEqual(self.batch.miriada_status_errors, {})

    @patch('filling_station.services.batches.post_status_to_miriada')
    def test_add_balloon_writes_miriada_error(self, mock_send):
        mock_send.side_effect = MiriadaAPIError('miriada down')
        result = add_balloon_to_batch_by_nfc(self.batch, self.balloon.nfc_tag)
        self.assertTrue(result['success'])
        self.batch.refresh_from_db()
        self.balloon.refresh_from_db()
        self.assertEqual(self.batch.rfid_balloon_count(), 1)
        self.assertEqual(self.balloon.miriada_status_error, 'miriada down')
        self.assertEqual(self.batch.miriada_status_errors, {self.balloon.nfc_tag: 'miriada down'})

        amount_url = reverse(
            'filling_station_api:balloons-loading-rfid-amount',
            args=[self.batch.id],
        )
        response = self.client.get(amount_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data['error_balloons'],
            [{
                'nfc_tag': self.balloon.nfc_tag,
                'serial_number': self.balloon.serial_number,
                'miriada_status_error': 'miriada down',
            }],
        )

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

    def test_send_immediately_only_for_filling_reader(self):
        self.assertFalse(should_send_balloon_status_immediately(6))
        self.assertFalse(should_send_balloon_status_immediately(3))
        self.assertTrue(should_send_balloon_status_immediately(8))

    @patch('ttn.services.close_ttn_in_miriada')
    @patch('filling_station.services.batches.post_status_to_miriada')
    def test_close_without_errors_calls_closettn(self, mock_send, mock_close):
        mock_close.return_value = (True, None)
        add_balloon_to_batch_by_nfc(self.batch, self.balloon.nfc_tag)
        mock_send.reset_mock()

        success, close_error = save_and_close_balloons_batch(self.batch)
        self.assertTrue(success)
        self.assertIsNone(close_error)
        mock_send.assert_not_called()
        mock_close.assert_called_once()
        self.batch.refresh_from_db()
        self.assertEqual(self.batch.status, BatchStatus.COMPLETED)
        self.assertEqual(self.batch.amount_of_ttn, 1)

    @patch('ttn.services.close_ttn_in_miriada')
    @patch('filling_station.services.batches.post_status_to_miriada')
    def test_close_rejected_when_rfid_does_not_match_ttn(self, mock_send, mock_close):
        success, error = save_and_close_balloons_batch(self.batch)
        self.assertFalse(success)
        self.assertTrue(error['count_mismatch'])
        mock_send.assert_not_called()
        mock_close.assert_not_called()
        self.batch.refresh_from_db()
        self.assertEqual(self.batch.status, BatchStatus.ACTIVE)

    @patch('ttn.services.close_ttn_in_miriada')
    @patch('filling_station.services.batches.post_status_to_miriada')
    def test_close_retries_only_error_balloons(self, mock_send, mock_close):
        mock_close.return_value = (True, None)
        ok_balloon = Balloon.objects.create(nfc_tag='okballon0001e0')
        bad_balloon = Balloon.objects.create(nfc_tag='badballon0001e0')

        def _send_on_add(url, payload, send_type, session=None):
            if payload['nfctag'] == bad_balloon.nfc_tag:
                raise MiriadaAPIError('-8')

        mock_send.side_effect = _send_on_add
        add_balloon_to_batch_by_nfc(self.batch, ok_balloon.nfc_tag)
        add_balloon_to_batch_by_nfc(self.batch, bad_balloon.nfc_tag)
        self.batch.amount_of_ttn = 2
        self.batch.save(update_fields=['amount_of_ttn'])
        self.assertEqual(mock_send.call_count, 2)

        mock_send.reset_mock()
        mock_send.side_effect = None

        success, close_error = save_and_close_balloons_batch(self.batch)
        self.assertTrue(success)
        self.assertIsNone(close_error)
        mock_send.assert_called_once()
        self.assertEqual(mock_send.call_args.args[1]['nfctag'], bad_balloon.nfc_tag)
        mock_close.assert_called_once()
        bad_balloon.refresh_from_db()
        self.assertEqual(bad_balloon.miriada_status_error, '')
        self.batch.refresh_from_db()
        self.assertEqual(self.batch.status, BatchStatus.COMPLETED)

    @patch('ttn.services.close_ttn_in_miriada')
    @patch('filling_station.services.batches.post_status_to_miriada')
    def test_close_fails_when_error_balloons_remain(self, mock_send, mock_close):
        mock_send.side_effect = MiriadaAPIError('-8')
        add_balloon_to_batch_by_nfc(self.batch, self.balloon.nfc_tag)
        mock_send.reset_mock()
        mock_send.side_effect = MiriadaAPIError('-8')

        success, error = save_and_close_balloons_batch(self.batch)
        self.assertFalse(success)
        self.assertTrue(error['balloon_status_errors'])
        mock_send.assert_called_once()
        mock_close.assert_not_called()
        self.batch.refresh_from_db()
        self.balloon.refresh_from_db()
        self.assertEqual(self.batch.status, BatchStatus.ACTIVE)
        self.assertEqual(self.balloon.miriada_status_error, '-8')

    @patch('ttn.services.close_ttn_in_miriada')
    @patch('filling_station.services.batches.post_status_to_miriada')
    def test_successful_retry_on_close_clears_balloon_error(self, mock_send, mock_close):
        mock_close.return_value = (True, None)
        mock_send.side_effect = MiriadaAPIError('-8')
        add_balloon_to_batch_by_nfc(self.batch, self.balloon.nfc_tag)
        self.balloon.refresh_from_db()
        self.assertEqual(self.balloon.miriada_status_error, '-8')

        mock_send.reset_mock()
        mock_send.side_effect = None

        success, close_error = save_and_close_balloons_batch(self.batch)
        self.assertTrue(success)
        self.assertIsNone(close_error)
        mock_send.assert_called_once()
        mock_close.assert_called_once()
        self.balloon.refresh_from_db()
        self.batch.refresh_from_db()
        self.assertEqual(self.balloon.miriada_status_error, '')
        self.assertEqual(self.batch.miriada_status_errors, {})
        self.assertEqual(self.batch.status, BatchStatus.COMPLETED)

    def test_remove_balloon_clears_miriada_status_error(self):
        with patch('filling_station.services.batches.post_status_to_miriada'):
            self.batch.add_balloon(self.balloon.nfc_tag)
        self.balloon.miriada_status_error = '-8'
        self.balloon.save(update_fields=['miriada_status_error'])
        self.batch.miriada_status_errors = {self.balloon.nfc_tag: '-8'}
        self.batch.miriada_balloons_sent = True
        self.batch.save(update_fields=['miriada_status_errors', 'miriada_balloons_sent'])

        result = self.batch.remove_balloon(self.balloon.nfc_tag)
        self.assertTrue(result['success'])
        self.batch.refresh_from_db()
        self.balloon.refresh_from_db()
        self.assertEqual(self.batch.miriada_status_errors, {})
        self.assertEqual(self.balloon.miriada_status_error, '')
        self.assertFalse(self.batch.miriada_balloons_sent)

    @patch('ttn.services.close_ttn_in_miriada')
    @patch('filling_station.services.batches.post_status_to_miriada')
    def test_close_from_miriada_error_without_balloon_errors(self, mock_send, mock_close):
        mock_close.return_value = (True, None)
        add_balloon_to_batch_by_nfc(self.batch, self.balloon.nfc_tag)
        self.batch.status = BatchStatus.MIRIADA_ERROR
        self.batch.save(update_fields=['status', 'miriada_close_failed'])
        mock_send.reset_mock()

        success, error = save_and_close_balloons_batch(self.batch)
        self.assertTrue(success)
        self.assertIsNone(error)
        mock_send.assert_not_called()
        mock_close.assert_called_once()
        self.batch.refresh_from_db()
        self.assertEqual(self.batch.status, BatchStatus.COMPLETED)

    def test_http_close_returns_400_on_count_mismatch(self):
        url = reverse('filling_station_api:balloons-loading-detail', args=[self.batch.id])
        response = self.client.patch(url, {'status': STATUS_TO_API[BatchStatus.COMPLETED]}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(response.data['count_mismatch'])
        self.batch.refresh_from_db()
        self.assertEqual(self.batch.status, BatchStatus.ACTIVE)

    @patch('ttn.services.close_ttn_in_miriada')
    @patch('filling_station.services.batches.post_status_to_miriada')
    def test_http_close_retries_errors_then_closes(self, mock_send, mock_close):
        mock_close.return_value = (True, None)
        mock_send.side_effect = MiriadaAPIError('-8')
        add_balloon_to_batch_by_nfc(self.batch, self.balloon.nfc_tag)
        mock_send.reset_mock()
        mock_send.side_effect = None

        url = reverse('filling_station_api:balloons-loading-detail', args=[self.batch.id])
        response = self.client.patch(url, {'status': STATUS_TO_API[BatchStatus.COMPLETED]}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_send.assert_called_once()
        mock_close.assert_called_once()
        self.batch.refresh_from_db()
        self.assertEqual(self.batch.status, BatchStatus.COMPLETED)

    def test_check_balloons_endpoint_removed(self):
        with self.assertRaises(NoReverseMatch):
            reverse('filling_station_api:balloons-loading-check-balloons', args=[self.batch.id])

    @patch('ttn.services.close_ttn_in_miriada')
    @patch('filling_station.services.batches.post_status_to_miriada')
    def test_http_close_returns_502_when_closettn_fails(self, mock_send, mock_close):
        mock_close.return_value = (False, 'Количество не соответствует указанному в ТТН')
        add_balloon_to_batch_by_nfc(self.batch, self.balloon.nfc_tag)
        mock_send.reset_mock()
        url = reverse('filling_station_api:balloons-loading-detail', args=[self.batch.id])
        response = self.client.patch(url, {'status': STATUS_TO_API[BatchStatus.COMPLETED]}, format='json')
        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)
        self.assertTrue(response.data['miriada_close_failed'])
        mock_send.assert_not_called()
        mock_close.assert_called_once()
        self.batch.refresh_from_db()
        self.assertEqual(self.batch.status, BatchStatus.MIRIADA_ERROR)

    def test_retry_close_returns_400_on_count_mismatch(self):
        url = reverse('filling_station_api:balloons-loading-retry-close', args=[self.batch.id])
        response = self.client.post(url, {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(response.data['count_mismatch'])
        self.batch.refresh_from_db()
        self.assertEqual(self.batch.status, BatchStatus.ACTIVE)

    @patch('ttn.services.close_ttn_in_miriada')
    @patch('filling_station.services.batches.post_status_to_miriada')
    def test_retry_close_success_equivalent_to_patch_close(self, mock_send, mock_close):
        mock_close.return_value = (True, None)
        add_balloon_to_batch_by_nfc(self.batch, self.balloon.nfc_tag)
        mock_send.reset_mock()
        url = reverse('filling_station_api:balloons-loading-retry-close', args=[self.batch.id])
        response = self.client.post(url, {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_close.assert_called_once()
        self.batch.refresh_from_db()
        self.assertEqual(self.batch.status, BatchStatus.COMPLETED)

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
        self.batch.amount_of_5_liters = 1
        self.batch.amount_of_12_liters = 2
        self.batch.amount_of_27_liters = 3
        self.batch.amount_of_50_liters = 4
        self.batch.save()
        self.assertEqual(self.batch.get_amount_without_rfid(), 10)

    @patch('filling_station.services.batches.post_status_to_miriada')
    def test_api_add_balloon_logs_action(self, mock_send):
        url = reverse('filling_station_api:balloons-loading-add-balloon', args=[self.batch.id])
        with self.assertLogs('filling_station', level='INFO') as logs:
            response = self.client.patch(url, {'nfc': self.balloon.nfc_tag}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(
            any('API add-balloon' in line and self.balloon.nfc_tag in line for line in logs.output)
        )
        mock_send.assert_called_once()

    def test_api_add_balloon_rejected_for_completed_batch(self):
        self.batch.status = BatchStatus.COMPLETED
        self.batch.save(update_fields=['status'])
        url = reverse('filling_station_api:balloons-loading-add-balloon', args=[self.batch.id])
        response = self.client.patch(url, {'nfc': self.balloon.nfc_tag}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('filling_station.services.batches.post_status_to_miriada')
    def test_api_add_balloon_conflict_when_already_in_batch(self, mock_send):
        url = reverse('filling_station_api:balloons-loading-add-balloon', args=[self.batch.id])
        first = self.client.patch(url, {'nfc': self.balloon.nfc_tag}, format='json')
        self.assertEqual(first.status_code, status.HTTP_200_OK)
        response = self.client.patch(url, {'nfc': self.balloon.nfc_tag}, format='json')
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertIn('уже в партии', response.data['message'])
        mock_send.assert_called_once()

    def test_api_add_balloon_not_found(self):
        url = reverse('filling_station_api:balloons-loading-add-balloon', args=[self.batch.id])
        response = self.client.patch(url, {'nfc': 'missingnfc0001'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_api_remove_balloon_not_in_batch(self):
        url = reverse('filling_station_api:balloons-loading-remove-balloon', args=[self.batch.id])
        response = self.client.patch(url, {'nfc': self.balloon.nfc_tag}, format='json')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @patch('filling_station.services.batches.post_status_to_miriada')
    def test_api_remove_balloon_allowed_for_miriada_error(self, mock_send):
        add_balloon_to_batch_by_nfc(self.batch, self.balloon.nfc_tag)
        self.batch.status = BatchStatus.MIRIADA_ERROR
        self.batch.save(update_fields=['status', 'miriada_close_failed'])
        url = reverse('filling_station_api:balloons-loading-remove-balloon', args=[self.batch.id])
        response = self.client.patch(url, {'nfc': self.balloon.nfc_tag}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.batch.refresh_from_db()
        self.assertFalse(self.batch.balloon_list.filter(nfc_tag=self.balloon.nfc_tag).exists())
        self.assertEqual(self.batch.rfid_balloon_count(), 0)

    @patch('filling_station.services.batches.post_status_to_miriada')
    def test_api_add_balloon_allowed_for_miriada_error(self, mock_send):
        self.batch.status = BatchStatus.MIRIADA_ERROR
        self.batch.save(update_fields=['status', 'miriada_close_failed'])
        url = reverse('filling_station_api:balloons-loading-add-balloon', args=[self.batch.id])
        response = self.client.patch(url, {'nfc': self.balloon.nfc_tag}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.batch.refresh_from_db()
        self.assertTrue(self.batch.balloon_list.filter(nfc_tag=self.balloon.nfc_tag).exists())
        self.assertEqual(self.batch.rfid_balloon_count(), 1)
        mock_send.assert_called_once()

    @patch('filling_station.services.batches.post_status_to_miriada')
    def test_api_add_balloon_succeeds_when_miriada_rejects(self, mock_send):
        mock_send.side_effect = MiriadaAPIError('-8')
        url = reverse('filling_station_api:balloons-loading-add-balloon', args=[self.batch.id])
        response = self.client.patch(url, {'nfc': self.balloon.nfc_tag}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.batch.refresh_from_db()
        self.balloon.refresh_from_db()
        self.assertTrue(self.batch.balloon_list.filter(nfc_tag=self.balloon.nfc_tag).exists())
        self.assertEqual(self.balloon.miriada_status_error, '-8')

    def test_web_remove_balloon_for_active_paused_and_miriada_error(self):
        for batch_status in (BatchStatus.ACTIVE, BatchStatus.PAUSED, BatchStatus.MIRIADA_ERROR):
            with self.subTest(status=batch_status):
                balloon = Balloon.objects.create(nfc_tag=f'remove{batch_status.value[:6]}e0')
                self.batch.status = BatchStatus.ACTIVE
                self.batch.save(update_fields=['status', 'miriada_close_failed'])
                with patch('filling_station.services.batches.post_status_to_miriada'):
                    self.batch.add_balloon(balloon.nfc_tag)
                self.batch.status = batch_status
                self.batch.save(update_fields=['status', 'miriada_close_failed'])
                amount_before = self.batch.rfid_balloon_count()

                url = reverse('filling_station:balloon_loading_batch_remove_balloon', args=[self.batch.id])
                response = self.client.post(url, {'nfc': balloon.nfc_tag})
                self.assertEqual(response.status_code, status.HTTP_302_FOUND)
                self.batch.refresh_from_db()
                self.assertFalse(self.batch.balloon_list.filter(nfc_tag=balloon.nfc_tag).exists())
                self.assertEqual(self.batch.rfid_balloon_count(), max(amount_before - 1, 0))

    def test_web_remove_balloon_rejected_for_completed(self):
        with patch('filling_station.services.batches.post_status_to_miriada'):
            self.batch.add_balloon(self.balloon.nfc_tag)
        self.batch.status = BatchStatus.COMPLETED
        self.batch.save(update_fields=['status', 'miriada_close_failed'])
        url = reverse('filling_station:balloon_loading_batch_remove_balloon', args=[self.batch.id])
        response = self.client.post(url, {'nfc': self.balloon.nfc_tag})
        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        self.batch.refresh_from_db()
        self.assertTrue(self.batch.balloon_list.filter(nfc_tag=self.balloon.nfc_tag).exists())
        self.assertEqual(self.batch.rfid_balloon_count(), 1)

    def test_web_remove_multiple_balloons(self):
        extra = Balloon.objects.create(nfc_tag='multirem0001e0')
        with patch('filling_station.services.batches.post_status_to_miriada'):
            self.batch.add_balloon(self.balloon.nfc_tag)
            self.batch.add_balloon(extra.nfc_tag)
        self.batch.miriada_status_errors = {
            self.balloon.nfc_tag: '-8',
            extra.nfc_tag: '-8',
        }
        self.batch.save(update_fields=['miriada_status_errors'])

        url = reverse('filling_station:balloon_loading_batch_remove_balloon', args=[self.batch.id])
        response = self.client.post(url, {'nfc': [self.balloon.nfc_tag, extra.nfc_tag]})
        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        self.batch.refresh_from_db()
        self.assertFalse(self.batch.balloon_list.filter(nfc_tag=self.balloon.nfc_tag).exists())
        self.assertFalse(self.batch.balloon_list.filter(nfc_tag=extra.nfc_tag).exists())
        self.assertEqual(self.batch.rfid_balloon_count(), 0)
        self.assertEqual(self.batch.miriada_status_errors, {})

    def test_web_remove_balloons_empty_nfc_list(self):
        with patch('filling_station.services.batches.post_status_to_miriada'):
            self.batch.add_balloon(self.balloon.nfc_tag)
        url = reverse('filling_station:balloon_loading_batch_remove_balloon', args=[self.batch.id])
        response = self.client.post(url, {})
        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        self.batch.refresh_from_db()
        self.assertTrue(self.batch.balloon_list.filter(nfc_tag=self.balloon.nfc_tag).exists())
        self.assertEqual(self.batch.rfid_balloon_count(), 1)

    def test_deleting_balloon_updates_rfid_count_from_list(self):
        with patch('filling_station.services.batches.post_status_to_miriada'):
            self.batch.add_balloon(self.balloon.nfc_tag)
        self.batch.refresh_from_db()
        self.assertEqual(self.batch.rfid_balloon_count(), 1)

        self.balloon.delete()
        self.batch.refresh_from_db()
        self.assertEqual(self.batch.rfid_balloon_count(), 0)
        self.assertEqual(self.batch.balloon_list.count(), 0)

        url = reverse('filling_station_api:balloons-loading-rfid-amount', args=[self.batch.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['amount_of_rfid'], 0)

    def test_balloon_operation_error_status_mapping(self):
        self.assertEqual(
            _balloon_operation_error_status('Баллон с меткой x уже в партии'),
            status.HTTP_409_CONFLICT,
        )
        self.assertEqual(
            _balloon_operation_error_status('Баллон с меткой x не найден в партии'),
            status.HTTP_404_NOT_FOUND,
        )
        self.assertEqual(
            _balloon_operation_error_status('Партия не принимает изменения в текущем статусе'),
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(
            _balloon_operation_error_status('Ошибка сервера: boom'),
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
