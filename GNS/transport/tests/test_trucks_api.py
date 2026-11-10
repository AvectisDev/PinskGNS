"""Тесты GET /api/trucks и фильтра on_station."""

from rest_framework import status
from rest_framework.test import APITestCase

from django.contrib.auth.models import User

from transport.models import Trailer, TrailerType, Truck, TruckType


class TrucksOnStationApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='reader', password='rfid-device')
        self.client.force_authenticate(self.user)
        self.truck_type = TruckType.objects.create(type='Трал')
        self.trailer_type = TrailerType.objects.create(type='Прицеп бортовой')
        self.on_station = Truck.objects.create(
            registration_number='AC 5512-1',
            type=self.truck_type,
            car_brand='МАЗ',
            is_on_station=True,
        )
        self.off_station = Truck.objects.create(
            registration_number='AP 1852-1',
            type=self.truck_type,
            car_brand='MAN',
            is_on_station=False,
        )
        Trailer.objects.create(
            truck=self.on_station,
            registration_number='A 5003K-1',
            type=self.trailer_type,
            is_on_station=True,
        )

    def test_list_without_filter_returns_all(self):
        response = self.client.get('/api/trucks')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        numbers = {item['registration_number'] for item in response.json()}
        self.assertEqual(numbers, {'AC 5512-1', 'AP 1852-1'})

    def test_legacy_on_station_query_returns_all_trucks(self):
        response = self.client.get('/api/trucks', {'on_station': 'true'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        numbers = {item['registration_number'] for item in response.json()}
        self.assertEqual(numbers, {'AC 5512-1', 'AP 1852-1'})

    def test_on_station_true_returns_only_trucks_on_station(self):
        response = self.client.get('/api/trucks/on-station')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['registration_number'], 'AC 5512-1')
        self.assertTrue(data[0]['is_on_station'])
        self.assertEqual(data[0]['trailer']['registration_number'], 'A 5003K-1')

    def test_on_station_true_returns_404_when_empty(self):
        self.on_station.is_on_station = False
        self.on_station.save(update_fields=['is_on_station'])
        response = self.client.get('/api/trucks/on-station')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(
            response.json(),
            {'detail': 'Грузовики с указанным фильтром не найдены'},
        )

    def test_on_station_ignores_trailer_status(self):
        """Прицеп на станции у тягача вне станции не попадает в on_station=true."""
        Trailer.objects.create(
            truck=self.off_station,
            registration_number='A 6922I-1',
            type=self.trailer_type,
            is_on_station=True,
        )
        response = self.client.get('/api/trucks/on-station')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        numbers = {item['registration_number'] for item in response.json()}
        self.assertEqual(numbers, {'AC 5512-1'})
        self.assertNotIn('AP 1852-1', numbers)
