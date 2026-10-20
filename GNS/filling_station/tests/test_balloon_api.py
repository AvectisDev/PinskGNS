"""API баллонов: get/create/statistic/counters/reader lists."""

from unittest.mock import patch

from django.core.cache import cache
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from filling_station.models import ReaderSettings, TotalReadersCounter
from filling_station.tests.factories import make_balloon, make_reader, make_user


# reverse для list остаётся; кастомные actions — по path (имена DRF нестабильны)


class BalloonApiTests(APITestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_authenticate(self.user)
        self.balloon = make_balloon(nfc_tag='api001e0', serial_number='S-API-1')

    def test_get_by_nfc_404_message(self):
        response = self.client.get('/api/balloons/nfc/missinge0/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('message', response.data)
        self.assertIn('не найден', response.data['message'])

    def test_get_by_serial_404_message(self):
        response = self.client.get('/api/balloons/serial-number/NO-SUCH/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('message', response.data)

    def test_create_conflict_on_duplicate_nfc(self):
        url = reverse('filling_station_api:balloons-list')
        response = self.client.post(
            url,
            {'nfc_tag': self.balloon.nfc_tag, 'size': 50},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertIn('message', response.data)

    def test_statistic_structure(self):
        for n in range(1, 9):
            ReaderSettings.objects.get_or_create(
                number=n,
                defaults={'ip': f'10.0.0.{n}', 'status': 'empty', 'function': 'p'},
            )
        TotalReadersCounter.objects.get_or_create(
            pk=1,
            defaults={'total_empty': 3, 'total_full': 7},
        )
        cache.delete('get_balloon_statistic')
        response = self.client.get('/api/balloons/statistic/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIsInstance(data, list)
        readers = [item for item in data if 'reader_id' in item]
        station = [item for item in data if 'filled_balloons_on_station' in item]
        self.assertEqual(len(readers), 8)
        self.assertEqual(len(station), 1)
        self.assertIn('empty_balloons_on_station', station[0])
        self.assertEqual(station[0]['filled_balloons_on_station'], 7)
        self.assertEqual(station[0]['empty_balloons_on_station'], 3)

    def test_manual_counter_values(self):
        TotalReadersCounter.objects.get_or_create(pk=1, defaults={'total_empty': 0, 'total_full': 0})
        response = self.client.post(
            '/api/total-readers-counter/manual-values',
            {'empty': 10, 'full': 4},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_empty'], 10)
        self.assertEqual(response.data['total_full'], 4)

    def test_manual_counter_requires_field(self):
        response = self.client.post(
            '/api/total-readers-counter/manual-values',
            {},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_loading_and_unloading_reader_lists(self):
        make_reader(6, function='l')
        make_reader(4, function='u')
        make_reader(1, function='p')
        loading = self.client.get('/api/loading-balloon-reader-list')
        unloading = self.client.get('/api/unloading-balloon-reader-list')
        self.assertEqual(loading.status_code, status.HTTP_200_OK)
        self.assertEqual(unloading.status_code, status.HTTP_200_OK)
        self.assertIn(6, loading.data)
        self.assertNotIn(4, loading.data)
        self.assertIn(4, unloading.data)
        self.assertNotIn(6, unloading.data)
