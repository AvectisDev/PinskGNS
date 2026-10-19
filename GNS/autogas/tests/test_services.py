from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from autogas.models import AutoGasBatch
from autogas.services import (
    ACTIVE_BATCH_CONSTRAINT,
    ActiveBatchExistsError,
    NoActiveBatchError,
    STATISTIC_CACHE_KEY,
    build_batch_statistic,
    cancel_active_batch,
    complete_active_batch,
    create_active_batch,
    get_batch_statistic,
    get_today_active_batches,
    get_truck_capacity,
    log_autogas_batch_status,
    log_autogas_numbers_snapshot,
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
    def test_cistern_uses_truck_mass(self):
        self.assertEqual(get_truck_capacity(self.truck), Decimal('20000'))

    def test_tractor_uses_trailer_mass(self):
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

    def test_cancel_active_batch(self):
        batch = self.make_batch(is_active=True)
        cancelled = cancel_active_batch()
        batch.refresh_from_db()
        self.assertEqual(cancelled.pk, batch.pk)
        self.assertFalse(batch.is_active)
        self.assertIsNotNone(batch.completed_at)

    def test_cancel_without_active_returns_none(self):
        self.assertIsNone(cancel_active_batch())

    def test_integrity_error_without_active_constraint_propagates(self):
        with patch(
            'autogas.services.AutoGasBatch.objects.create',
            side_effect=IntegrityError('fk_user_id'),
        ):
            with self.assertRaises(IntegrityError):
                create_active_batch(
                    batch_type='l',
                    gas_type='ПБА',
                    truck=self.truck,
                )

    def test_integrity_error_active_constraint_maps_to_active_exists(self):
        with patch(
            'autogas.services.AutoGasBatch.objects.create',
            side_effect=IntegrityError(ACTIVE_BATCH_CONSTRAINT),
        ):
            with self.assertRaises(ActiveBatchExistsError):
                create_active_batch(
                    batch_type='l',
                    gas_type='ПБА',
                    truck=self.truck,
                )

    def test_deactivate_payload_sets_completed_at(self):
        payload = with_completed_at_on_deactivate({'is_active': False, 'gas_amount': 1})
        self.assertFalse(payload['is_active'])
        self.assertIn('completed_at', payload)

    def test_deactivate_payload_keeps_active_untouched(self):
        payload = with_completed_at_on_deactivate({'gas_amount': 1})
        self.assertNotIn('completed_at', payload)


class StatisticServiceTests(AutoGasFixturesMixin, TestCase):
    def _assert_zero_loading(self, bucket):
        self.assertEqual(bucket['last_month_loading_batches'], 0)
        self.assertEqual(bucket['last_month_loading_weight'], 0)
        self.assertEqual(bucket['today_loading_batches'], 0)
        self.assertEqual(bucket['today_loading_weight'], 0)

    def _assert_zero_unloading(self, bucket):
        self.assertEqual(bucket['last_month_unloading_batches'], 0)
        self.assertEqual(bucket['last_month_unloading_weight'], 0)
        self.assertEqual(bucket['today_unloading_batches'], 0)
        self.assertEqual(bucket['today_unloading_weight'], 0)

    def test_empty_statistic(self):
        data = build_batch_statistic()
        self.assertEqual(set(data['loading_batch']), {'СПБТ', 'ПБА'})
        self.assertEqual(set(data['unloading_batch']), {'СПБТ', 'ПБА'})
        for gas_type in ('СПБТ', 'ПБА'):
            loading = data['loading_batch'][gas_type]
            unloading = data['unloading_batch'][gas_type]
            self.assertEqual(loading['gas_type'], gas_type)
            self.assertEqual(loading['batch_type'], 'l')
            self._assert_zero_loading(loading)
            self.assertEqual(unloading['gas_type'], gas_type)
            self.assertEqual(unloading['batch_type'], 'u')
            self._assert_zero_unloading(unloading)
        self.assertNotIn('active_batch', data)

    def test_aggregates_month_and_today(self):
        # Фиксируем «сегодня» серединой месяца, чтобы партия «раньше» оставалась
        # в том же календарном месяце на любой дате прогона.
        today = date(2026, 6, 15)
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
        AutoGasBatch.objects.filter(pk=today_batch.pk).update(
            begin_at=timezone.make_aware(datetime(2026, 6, 15, 12, 0, 0)),
        )
        AutoGasBatch.objects.filter(pk=earlier.pk).update(
            begin_at=timezone.make_aware(datetime(2026, 6, 10, 12, 0, 0)),
        )

        data = build_batch_statistic(today=today)
        pba = data['loading_batch']['ПБА']
        self.assertEqual(pba['today_loading_batches'], 1)
        self.assertEqual(pba['today_loading_weight'], Decimal('1000'))
        self.assertEqual(pba['last_month_loading_batches'], 2)
        self.assertEqual(pba['last_month_loading_weight'], Decimal('3000'))
        self.assertEqual(today_batch.gas_type, 'ПБА')

    def test_partial_month_data_keeps_zero_fields(self):
        """Партия только за прошлый день месяца: today_* и СПБТ/отгрузка = 0."""
        today = date(2026, 6, 15)
        earlier = self.make_batch(
            batch_type='l',
            gas_type='ПБА',
            weight_gas_amount=Decimal('2000'),
        )
        AutoGasBatch.objects.filter(pk=earlier.pk).update(
            begin_at=timezone.make_aware(datetime(2026, 6, 10, 12, 0, 0)),
        )

        data = build_batch_statistic(today=today)
        pba = data['loading_batch']['ПБА']
        self.assertEqual(pba['last_month_loading_batches'], 1)
        self.assertEqual(pba['last_month_loading_weight'], Decimal('2000'))
        self.assertEqual(pba['today_loading_batches'], 0)
        self.assertEqual(pba['today_loading_weight'], 0)
        self._assert_zero_loading(data['loading_batch']['СПБТ'])
        self._assert_zero_unloading(data['unloading_batch']['ПБА'])
        self._assert_zero_unloading(data['unloading_batch']['СПБТ'])

    def test_null_weight_becomes_zero(self):
        today = date(2026, 6, 15)
        batch = self.make_batch(
            batch_type='u',
            gas_type='СПБТ',
            weight_gas_amount=None,
        )
        AutoGasBatch.objects.filter(pk=batch.pk).update(
            begin_at=timezone.make_aware(datetime(2026, 6, 15, 12, 0, 0)),
        )

        data = build_batch_statistic(today=today)
        spbt = data['unloading_batch']['СПБТ']
        self.assertEqual(spbt['today_unloading_batches'], 1)
        self.assertEqual(spbt['today_unloading_weight'], 0)
        self.assertIsNotNone(spbt['today_unloading_weight'])

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


@override_settings(CACHES={
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'autogas-log-snapshot-tests',
    }
})
class AutoGasLogSnapshotTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    @patch('autogas.services.logger')
    def test_batch_status_logged_only_when_changed(self, logger):
        idle = {
            'batch_type_code': 2,
            'gas_type': 2,
            'request_batch_create': False,
            'request_batch_complete': False,
        }
        log_autogas_batch_status(idle)
        log_autogas_batch_status(idle)
        logger.debug.assert_called_once_with(
            'Тип партии=2, Тип газа=2, Запрос создания=False, Запрос завершения=False'
        )

        creating = {**idle, 'request_batch_create': True}
        log_autogas_batch_status(creating)
        self.assertEqual(logger.debug.call_count, 2)
        logger.debug.assert_called_with(
            'Тип партии=2, Тип газа=2, Запрос создания=True, Запрос завершения=False'
        )

    @patch('autogas.services.logger')
    def test_empty_and_unchanged_numbers_are_not_logged(self, logger):
        log_autogas_numbers_snapshot([])
        log_autogas_numbers_snapshot([])
        logger.debug.assert_not_called()

        log_autogas_numbers_snapshot(['AC17911', 'AP75311'])
        log_autogas_numbers_snapshot(['AC17911', 'AP75311'])
        logger.debug.assert_called_once_with(
            "Список номеров: ['AC17911', 'AP75311']"
        )

        log_autogas_numbers_snapshot([])
        self.assertEqual(logger.debug.call_count, 1)
        log_autogas_numbers_snapshot(['AC17911', 'AP75311'])
        self.assertEqual(logger.debug.call_count, 2)
