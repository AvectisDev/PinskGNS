from datetime import datetime

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from autogas.models import AutoGasBatch
from .helpers import AutoGasFixturesMixin


class AutoGasBatchViewTests(AutoGasFixturesMixin, TestCase):
    def test_list_single_date_does_not_filter(self):
        today = timezone.localdate()
        current = self.make_batch()
        old = self.make_batch(truck=self.tractor)
        AutoGasBatch.objects.filter(pk=old.pk).update(
            begin_at=timezone.make_aware(datetime(2020, 1, 1, 10, 0)),
        )
        url = reverse('autogas:auto_gas_batch_list')
        response = self.client.get(url, {'start_date': today.isoformat()})
        self.assertEqual(response.status_code, 200)
        ids = set(response.context['page_obj'].object_list.values_list('id', flat=True))
        self.assertEqual(ids, {current.pk, old.pk})

    def test_list_invalid_date_does_not_filter(self):
        current = self.make_batch()
        old = self.make_batch(truck=self.tractor)
        AutoGasBatch.objects.filter(pk=old.pk).update(
            begin_at=timezone.make_aware(datetime(2020, 1, 1, 10, 0)),
        )
        url = reverse('autogas:auto_gas_batch_list')
        response = self.client.get(url, {
            'start_date': 'not-a-date',
            'end_date': 'also-bad',
        })
        self.assertEqual(response.status_code, 200)
        ids = set(response.context['page_obj'].object_list.values_list('id', flat=True))
        self.assertEqual(ids, {current.pk, old.pk})

    def test_list_paginates_second_page(self):
        for i in range(11):
            self.make_batch(
                truck=self.truck if i % 2 == 0 else self.tractor,
            )
        url = reverse('autogas:auto_gas_batch_list')
        response = self.client.get(url, {'page': 2})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['is_paginated'])
        self.assertEqual(len(response.context['page_obj'].object_list), 1)

    def test_detail_shows_loading_active_badges(self):
        batch = self.make_batch(batch_type='l', is_active=True)
        url = reverse('autogas:auto_gas_batch_detail', args=[batch.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('Приёмка', content)
        self.assertIn('Активна', content)

    def test_detail_shows_unloading_completed_badges(self):
        batch = self.make_batch(batch_type='u', is_active=False)
        url = reverse('autogas:auto_gas_batch_detail', args=[batch.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('Отгрузка', content)
        self.assertIn('Завершена', content)

    def test_detail_missing_returns_404(self):
        url = reverse('autogas:auto_gas_batch_detail', args=[999999])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_update_get_includes_title(self):
        batch = self.make_batch()
        url = reverse('autogas:auto_gas_batch_update', args=[batch.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context['title'],
            'Редактирование партии приёмки/отгрузки газа в автоцистернах',
        )

    def test_update_cancel_redirects_without_changes(self):
        batch = self.make_batch(gas_type='СПБТ')
        url = reverse('autogas:auto_gas_batch_update', args=[batch.pk])
        response = self.client.post(url, {
            'cancel': 'Отмена',
            'batch_type': 'u',
            'truck': self.truck.pk,
            'gas_type': 'ПБА',
            'is_active': False,
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url,
            reverse('autogas:auto_gas_batch_detail', args=[batch.pk]),
        )
        batch.refresh_from_db()
        self.assertEqual(batch.gas_type, 'СПБТ')

    def test_update_valid_post_saves_and_redirects(self):
        batch = self.make_batch(gas_type='СПБТ', is_active=False)
        url = reverse('autogas:auto_gas_batch_update', args=[batch.pk])
        response = self.client.post(url, {
            'save': 'Сохранить',
            'batch_type': 'u',
            'truck': self.truck.pk,
            'gas_type': 'ПБА',
            'is_active': False,
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url,
            reverse('autogas:auto_gas_batch_detail', args=[batch.pk]),
        )
        batch.refresh_from_db()
        self.assertEqual(batch.batch_type, 'u')
        self.assertEqual(batch.gas_type, 'ПБА')

    def test_update_invalid_post_stays_200(self):
        batch = self.make_batch()
        self.make_batch(is_active=True, truck=self.tractor)
        url = reverse('autogas:auto_gas_batch_update', args=[batch.pk])
        response = self.client.post(url, {
            'save': 'Сохранить',
            'batch_type': 'l',
            'truck': self.truck.pk,
            'gas_type': 'СПБТ',
            'is_active': True,
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form'].errors)

    def test_update_deactivate_does_not_set_completed_at(self):
        batch = self.make_batch(is_active=True)
        url = reverse('autogas:auto_gas_batch_update', args=[batch.pk])
        response = self.client.post(url, {
            'save': 'Сохранить',
            'batch_type': 'l',
            'truck': self.truck.pk,
            'gas_type': 'СПБТ',
            # is_active отсутствует в POST → False
        })
        self.assertEqual(response.status_code, 302)
        batch.refresh_from_db()
        self.assertFalse(batch.is_active)
        self.assertIsNone(batch.completed_at)

    def test_delete_get_redirects_without_deleting(self):
        batch = self.make_batch()
        url = reverse('autogas:auto_gas_batch_delete', args=[batch.pk])
        list_url = reverse('autogas:auto_gas_batch_list')
        response = self.client.get(url, HTTP_REFERER=list_url)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(AutoGasBatch.objects.filter(pk=batch.pk).exists())

    def test_delete_post_removes_and_redirects_to_list(self):
        batch = self.make_batch()
        url = reverse('autogas:auto_gas_batch_delete', args=[batch.pk])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('autogas:auto_gas_batch_list'))
        self.assertFalse(AutoGasBatch.objects.filter(pk=batch.pk).exists())

    def test_delete_missing_post_returns_404(self):
        url = reverse('autogas:auto_gas_batch_delete', args=[999999])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 404)
