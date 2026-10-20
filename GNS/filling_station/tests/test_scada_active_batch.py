"""Тесты SCADA endpoint GET /api/get-active-balloon-batch."""

from rest_framework import status
from rest_framework.test import APITestCase

from filling_station.models import BatchStatus
from filling_station.tests.factories import (
    make_batch,
    make_reader,
    make_trailer,
    make_truck,
    make_user,
)


class ScadaActiveBalloonBatchTests(APITestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_authenticate(self.user)
        self.truck_l = make_truck(registration_number='AC 5512-1')
        self.truck_u = make_truck(registration_number='AP 1852-1')
        self.trailer = make_trailer(truck=self.truck_u, registration_number='A 5003K-1')
        make_reader(6, function='l')
        make_reader(4, function='u')

    def test_returns_only_today_active_loading_and_unloading(self):
        make_batch(
            batch_type='l',
            truck=self.truck_l,
            reader_number=6,
            status=BatchStatus.ACTIVE,
            user=self.user,
        )
        make_batch(
            batch_type='u',
            truck=self.truck_u,
            trailer=self.trailer,
            reader_number=4,
            status=BatchStatus.ACTIVE,
            user=self.user,
            ttn_id=57097,
        )
        make_batch(
            batch_type='l',
            truck=self.truck_l,
            reader_number=6,
            status=BatchStatus.PAUSED,
            user=self.user,
            ttn_id=111,
        )
        make_batch(
            batch_type='u',
            truck=self.truck_u,
            reader_number=4,
            status=BatchStatus.COMPLETED,
            user=self.user,
            ttn_id=222,
        )

        response = self.client.get('/api/get-active-balloon-batch')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(len(data), 2)
        by_reader = {item['reader_id']: item for item in data}
        self.assertEqual(by_reader[6]['truck_registration_number'], 'AC 5512-1')
        self.assertEqual(by_reader[6]['trailer_registration_number'], '')
        self.assertEqual(by_reader[4]['truck_registration_number'], 'AP 1852-1')
        self.assertEqual(by_reader[4]['trailer_registration_number'], 'A 5003K-1')

    def test_empty_list_when_no_active(self):
        make_batch(
            batch_type='l',
            truck=self.truck_l,
            reader_number=6,
            status=BatchStatus.PAUSED,
            user=self.user,
        )
        response = self.client.get('/api/get-active-balloon-batch')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), [])
