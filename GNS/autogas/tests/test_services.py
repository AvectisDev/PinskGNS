from datetime import timedelta
from decimal import Decimal

from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.utils import timezone

from autogas.models import AutoGasBatch
from autogas.services import (
    ActiveBatchExistsError,
    NoActiveBatchError,
    STATISTIC_CACHE_KEY,
    build_batch_statistic,
    complete_active_batch,
    create_active_batch,
    get_batch_statistic,
    get_today_active_batches,
    get_truck_capacity,
    resolve_batch_type,
    resolve_gas_type,
    with_completed_at_on_deactivate,
)
from .helpers import AutoGasFixturesMixin


class ResolveTypeTests(AutoGasFixturesMixin, TestCase):
    def test_resolve_gas_type_accepts_only_settings_values(self):
        self.assertEqual(resolve_gas_type(2), 'СПБТ')
        self.assertEqual(resolve_gas_type(3), 'ПБА')
        self.assertIsNone(resolve_gas_type(1))
        self.assertIsNone(resolve_gas_type(None))

    def test_resolve_batch_type(self):
        self.assertEqual(resolve_batch_type(1), 'l')
        self.assertEqual(resolve_batch_type(2), 'u')
        self.assertIsNone(resolve_batch_type(0))


class TruckCapacityTests(AutoGasFixturesMixin, TestCase):
    def test_cistern_uses_truck_volume(self):
        self.assertEqual(get_truck_capacity(self.truck), Decimal('20000'))

    def test_tractor_uses_trailer_volume(self):
        self.assertEqual(
            get_truck_capacity(self.tractor, self.trailer),
            Decimal('18000'),
        )

    def test_unknown_type_returns_none(self):
        self.truck.type.type = 'Клетевоз'
        self.assertIsNone(get_truck_capacity(self.truck))


class ActiveBatchServiceTests(AutoGasFixturesMixin, TestCase):
    def test_create_active_batch(self):
        batch = create_active_batch(
            batch_type='l',
            gas_type='ПБА',
            truck=self.truck,
        )
        self.assertTrue(batch.is_active)
        self.assertEqual(batch.gas_type, 'ПБА')
        self.assertEqual(batch.truck, self.truck)

    def test_create_rejects_second_active_batch(self):
        create_active_batch(
            batch_type='l',
            gas_type='СПБТ',
            truck=self.truck,
        )
        with self.assertRaises(ActiveBatchExistsError):
            create_active_batch(
                batch_type='u',
                gas_type='ПБА',
                truck=self.tractor,
            )
        self.assertEqual(AutoGasBatch.objects.filter(is_active=True).count(), 1)

    def test_unique_constraint_blocks_second_active(self):
        self.make_batch(is_active=True)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.make_batch(is_active=True, truck=self.tractor)

    def test_complete_active_batch(self):
        batch = self.make_batch(is_active=True)
        completed = complete_active_batch({
            'gas_amount': Decimal('10.50'),
            'truck_empty_weight': Decimal('15000'),
            'truck_full_weight': Decimal('25000'),
            'weight_gas_amount': Decimal('10000'),
        })
        batch.refresh_from_db()
        self.assertEqual(completed.pk, batch.pk)
        self.assertFalse(batch.is_active)
        self.assertEqual(batch.gas_amount, Decimal('10.50'))
        self.assertEqual(batch.weight_gas_amount, Decimal('10000'))
        self.assertIsNotNone(batch.completed_at)

    def test_complete_without_active_batch(self):
        with self.assertRaises(NoActiveBatchError):
            complete_active_batch({'gas_amount': 1})

    def test_deactivate_payload_sets_completed_at(self):
        payload = with_completed_at_on_deactivate({'is_active': False, 'gas_amount': 1})
        self.assertFalse(payload['is_active'])
        self.assertIn('completed_at', payload)

    def test_deactivate_payload_keeps_active_untouched(self):
        payload = with_completed_at_on_deactivate({'gas_amount': 1})
        self.assertNotIn('completed_at', payload)


class StatisticServiceTests(AutoGasFixturesMixin, TestCase):
    def test_empty_statistic(self):
        data = build_batch_statistic()
        self.assertEqual(data['loading_batch'], {})
        self.assertEqual(data['unloading_batch'], {})
        self.assertNotIn('active_batch', data)

    def test_aggregates_month_and_today(self):
        today_batch = self.make_batch(
            batch_type='l',
            gas_type='ПБА',
            weight_gas_amount=Decimal('1000'),
        )
        earlier = self.make_batch(
            batch_type='l',
            gas_type='ПБА',
            weight_gas_amount=Decimal('2000'),
            truck=self.tractor,
        )
        AutoGasBatch.objects.filter(pk=earlier.pk).update(
            begin_at=timezone.now() - timedelta(days=5),
        )

        data = build_batch_statistic()
        pba = data['loading_batch']['ПБА']
        self.assertEqual(pba['today_loading_batches'], 1)
        self.assertEqual(pba['today_loading_weight'], Decimal('1000'))
        self.assertEqual(pba['last_month_loading_batches'], 2)
        self.assertEqual(pba['last_month_loading_weight'], Decimal('3000'))
        self.assertEqual(today_batch.gas_type, 'ПБА')

    def test_active_batch_payload(self):
        self.make_batch(
            is_active=True,
            batch_type='l',
            gas_type='ПБА',
            trailer=self.trailer,
            scale_empty_weight=Decimal('15000'),
            scale_full_weight=Decimal('35000'),
        )
        data = build_batch_statistic()
        active = data['active_batch']
        self.assertEqual(active['batch_type'], 'Приёмка')
        self.assertEqual(active['gas_type'], 'ПБА')
        self.assertEqual(active['truck_number'], self.truck.registration_number)
        self.assertEqual(active['trailer_number'], self.trailer.registration_number)
        self.assertEqual(active['truck_gas_capacity'], Decimal('20000'))
        self.assertEqual(active['scale_empty_weight'], Decimal('15000'))

    def test_today_active_batches_excludes_yesterday(self):
        batch = self.make_batch(is_active=True)
        AutoGasBatch.objects.filter(pk=batch.pk).update(
            begin_at=timezone.now() - timedelta(days=1),
        )
        self.assertEqual(list(get_today_active_batches()), [])

    def test_get_period_stats_returns_zeros(self):
        stats = AutoGasBatch.get_period_stats(
            start_date=timezone.localdate(),
            end_date=timezone.localdate(),
        )
        self.assertEqual(stats['loading_batches'], 0)
        self.assertEqual(stats['total_gas_loading_by_weight'], 0)


@override_settings(CACHES={
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'autogas-statistic-tests',
    }
})
class StatisticCacheTests(AutoGasFixturesMixin, TestCase):
    def setUp(self):
        super().setUp()
        cache.clear()

    def test_statistic_uses_cache(self):
        self.make_batch(batch_type='u', gas_type='СПБТ', weight_gas_amount=5)
        get_batch_statistic()
        cache.set(
            STATISTIC_CACHE_KEY,
            {'loading_batch': {'cached': True}, 'unloading_batch': {}},
        )
        cached = get_batch_statistic()
        self.assertEqual(cached['loading_batch'], {'cached': True})
        cache.delete(STATISTIC_CACHE_KEY)
        fresh = get_batch_statistic()
        self.assertEqual(
            fresh['unloading_batch']['СПБТ']['today_unloading_batches'],
            1,
        )
