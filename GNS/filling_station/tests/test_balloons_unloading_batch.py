"""API тесты партий отгрузки (balloons-unloading)."""

from unittest.mock import patch

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from filling_station.api.batch_status import STATUS_TO_API
from filling_station.exceptions import MiriadaAPIError
from filling_station.models import BatchStatus
from filling_station.tests.factories import (
    make_balloon,
    make_batch,
    make_reader,
    make_truck,
    make_user,
)


class BalloonsUnloadingBatchTests(APITestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_authenticate(self.user)
        self.truck = make_truck(registration_number='AP 1852-1', type_name='Трал')
        make_reader(4, function='u')
        self.batch = make_batch(
            batch_type='u',
            truck=self.truck,
            reader_number=4,
            ttn_id=57097,
            amount_of_ttn=1,
            user=self.user,
        )
        self.balloon = make_balloon(nfc_tag='unload001e0')

    def test_create_unloading_batch(self):
        url = reverse('filling_station_api:balloons-unloading-list')
        response = self.client.post(
            url,
            {
                'truck': self.truck.id,
                'reader_number': 4,
                'ttn_id': 57100,
                'amount_of_ttn': 5,
                'balloons_type': 'f',
                'status': STATUS_TO_API[BatchStatus.ACTIVE],
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['batch_type'], 'u')
        self.assertEqual(response.data['amount_of_ttn'], 5)

    @patch('filling_station.services.batches.post_status_to_miriada')
    def test_add_balloon_sends_balloontocar_payload(self, mock_post):
        url = reverse(
            'filling_station_api:balloons-unloading-add-balloon',
            args=[self.batch.id],
        )
        response = self.client.patch(url, {'nfc': self.balloon.nfc_tag}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_post.assert_called_once()
        _url, payload, send_type = mock_post.call_args[0][:3]
        # call may be positional via prepare then post — check kwargs/args from add path
        # post_status_to_miriada(url, payload, send_type)
        self.assertEqual(send_type, 'loading_into_truck')
        self.assertEqual(payload['number_auto'], 'AP 1852-1')
        self.assertEqual(payload['id_ttn'], 57097)

    @patch('filling_station.services.batches.post_status_to_miriada')
    def test_add_balloon_403_stores_human_error_keeps_balloon(self, mock_post):
        mock_post.side_effect = MiriadaAPIError('Автомобиль не найден')
        url = reverse(
            'filling_station_api:balloons-unloading-add-balloon',
            args=[self.batch.id],
        )
        response = self.client.patch(url, {'nfc': self.balloon.nfc_tag}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.balloon.refresh_from_db()
        self.assertEqual(self.balloon.miriada_status_error, 'Автомобиль не найден')
        self.batch.refresh_from_db()
        self.assertTrue(
            self.batch.balloon_list.filter(nfc_tag=self.balloon.nfc_tag).exists()
        )

    def test_close_count_mismatch(self):
        url = reverse(
            'filling_station_api:balloons-unloading-detail',
            args=[self.batch.id],
        )
        response = self.client.patch(
            url,
            {'status': STATUS_TO_API[BatchStatus.COMPLETED]},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(response.data['count_mismatch'])

    @patch('ttn.services.close_ttn_in_miriada')
    @patch('filling_station.services.batches.post_status_to_miriada')
    def test_close_success(self, mock_send, mock_close):
        mock_close.return_value = (True, None)
        with patch('filling_station.services.batches.post_status_to_miriada'):
            from filling_station.services.batches import add_balloon_to_batch_by_nfc
            add_balloon_to_batch_by_nfc(self.batch, self.balloon.nfc_tag)
        mock_send.reset_mock()
        url = reverse(
            'filling_station_api:balloons-unloading-detail',
            args=[self.batch.id],
        )
        response = self.client.patch(
            url,
            {'status': STATUS_TO_API[BatchStatus.COMPLETED]},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_close.assert_called_once()
        self.batch.refresh_from_db()
        self.assertEqual(self.batch.status, BatchStatus.COMPLETED)

    @patch('ttn.services.close_ttn_in_miriada')
    @patch('filling_station.services.batches.post_status_to_miriada')
    def test_close_502_on_closettn_fail(self, mock_send, mock_close):
        mock_close.return_value = (False, 'closettn failed')
        with patch('filling_station.services.batches.post_status_to_miriada'):
            from filling_station.services.batches import add_balloon_to_batch_by_nfc
            add_balloon_to_batch_by_nfc(self.batch, self.balloon.nfc_tag)
        mock_send.reset_mock()
        url = reverse(
            'filling_station_api:balloons-unloading-detail',
            args=[self.batch.id],
        )
        response = self.client.patch(
            url,
            {'status': STATUS_TO_API[BatchStatus.COMPLETED]},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)
        self.assertTrue(response.data['miriada_close_failed'])
        self.batch.refresh_from_db()
        self.assertEqual(self.batch.status, BatchStatus.MIRIADA_ERROR)
