from datetime import timedelta
from decimal import Decimal

from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
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

    def test_create_inactive_returns_201(self):
        url = reverse('autogas_api:auto-gas-batch-list')
        response = self.client.post(url, {
            'batch_type': 'l',
            'truck': self.truck.pk,
            'gas_type': 'СПБТ',
            'is_active': False,
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertFalse(AutoGasBatch.objects.get(pk=response.data['id']).is_active)

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

    def test_partial_update_overrides_client_completed_at(self):
        batch = self.make_batch(is_active=True)
        url = reverse('autogas_api:auto-gas-batch-detail', args=[batch.pk])
        old = (timezone.now() - timedelta(days=5)).isoformat()
        response = self.client.patch(url, {
            'is_active': False,
            'completed_at': old,
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        batch.refresh_from_db()
        self.assertFalse(batch.is_active)
        self.assertIsNotNone(batch.completed_at)
        self.assertGreater(batch.completed_at, timezone.now() - timedelta(minutes=1))

    def test_partial_update_without_deactivate_keeps_completed_at(self):
        batch = self.make_batch(is_active=True, gas_type='СПБТ')
        url = reverse('autogas_api:auto-gas-batch-detail', args=[batch.pk])
        response = self.client.patch(url, {'gas_type': 'ПБА'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        batch.refresh_from_db()
        self.assertTrue(batch.is_active)
        self.assertIsNone(batch.completed_at)
        self.assertEqual(batch.gas_type, 'ПБА')

    def test_partial_update_missing_returns_404(self):
        url = reverse('autogas_api:auto-gas-batch-detail', args=[999999])
        response = self.client.patch(url, {'is_active': False}, format='json')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_partial_update_invalid_gas_type_returns_400(self):
        batch = self.make_batch(is_active=True)
        url = reverse('autogas_api:auto-gas-batch-detail', args=[batch.pk])
        response = self.client.patch(url, {'gas_type': 'Не выбран'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_partial_update_second_active_returns_400(self):
        self.make_batch(is_active=True)
        other = self.make_batch(is_active=False, truck=self.tractor)
        url = reverse('autogas_api:auto-gas-batch-detail', args=[other.pk])
        response = self.client.patch(url, {'is_active': True}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('is_active', response.data)

    def test_list_returns_today_active(self):
        active = self.make_batch(is_active=True)
        self.make_batch(is_active=False, truck=self.tractor)
        url = reverse('autogas_api:auto-gas-batch-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['id'], active.pk)

    def test_list_excludes_yesterday_active(self):
        batch = self.make_batch(is_active=True)
        AutoGasBatch.objects.filter(pk=batch.pk).update(
            begin_at=timezone.now() - timedelta(days=1),
        )
        url = reverse('autogas_api:auto-gas-batch-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, [])

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

    def test_unauthenticated_post_rejected(self):
        self.client.force_authenticate(user=None)
        url = reverse('autogas_api:auto-gas-batch-list')
        response = self.client.post(url, {
            'batch_type': 'l',
            'truck': self.truck.pk,
            'gas_type': 'СПБТ',
        }, format='json')
        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )

    def test_unauthenticated_patch_rejected(self):
        batch = self.make_batch(is_active=True)
        self.client.force_authenticate(user=None)
        url = reverse('autogas_api:auto-gas-batch-detail', args=[batch.pk])
        response = self.client.patch(url, {'is_active': False}, format='json')
        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )

    def test_detail_methods_not_allowed(self):
        batch = self.make_batch()
        url = reverse('autogas_api:auto-gas-batch-detail', args=[batch.pk])
        for method in ('get', 'put', 'delete'):
            response = getattr(self.client, method)(url, format='json')
            self.assertEqual(
                response.status_code,
                status.HTTP_405_METHOD_NOT_ALLOWED,
                msg=method,
            )
