from decimal import Decimal

from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from autogas.models import AutoGasBatch
from .helpers import AutoGasFixturesMixin


@override_settings(CACHES={
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'autogas-api-tests',
    }
})
class AutoGasBatchAPITests(AutoGasFixturesMixin, APITestCase):
    def setUp(self):
        super().setUp()
        self.client.force_authenticate(self.user)

    def test_create_returns_201(self):
        url = reverse('autogas_api:auto-gas-batch-list')
        response = self.client.post(url, {
            'batch_type': 'l',
            'truck': self.truck.pk,
            'gas_type': 'ПБА',
            'is_active': True,
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(AutoGasBatch.objects.filter(is_active=True).exists())

    def test_create_returns_400_on_invalid_gas_type(self):
        url = reverse('autogas_api:auto-gas-batch-list')
        response = self.client.post(url, {
            'batch_type': 'l',
            'truck': self.truck.pk,
            'gas_type': 'Не выбран',
            'is_active': True,
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_second_active_returns_400(self):
        self.make_batch(is_active=True)
        url = reverse('autogas_api:auto-gas-batch-list')
        response = self.client.post(url, {
            'batch_type': 'u',
            'truck': self.tractor.pk,
            'gas_type': 'СПБТ',
            'is_active': True,
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('is_active', response.data)

    def test_partial_update_sets_completed_at(self):
        batch = self.make_batch(is_active=True)
        url = reverse('autogas_api:auto-gas-batch-detail', args=[batch.pk])
        response = self.client.patch(url, {'is_active': False}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        batch.refresh_from_db()
        self.assertFalse(batch.is_active)
        self.assertIsNotNone(batch.completed_at)

    def test_list_returns_today_active(self):
        active = self.make_batch(is_active=True)
        self.make_batch(is_active=False, truck=self.tractor)
        url = reverse('autogas_api:auto-gas-batch-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['id'], active.pk)

    def test_statistic_includes_active_batch(self):
        self.make_batch(
            is_active=True,
            batch_type='u',
            gas_type='СПБТ',
            weight_gas_amount=Decimal('500'),
        )
        url = reverse('autogas_api:auto-gas-batch-statistic')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['active_batch']['batch_type'], 'Отгрузка')
        self.assertEqual(
            response.data['unloading_batch']['СПБТ']['today_unloading_batches'],
            1,
        )

    def test_unauthenticated_rejected(self):
        self.client.force_authenticate(user=None)
        url = reverse('autogas_api:auto-gas-batch-list')
        response = self.client.get(url)
        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )
