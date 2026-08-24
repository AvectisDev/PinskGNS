from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from railway_service.models import RailwayTankHistory

from .helpers import RailwayFixturesMixin


class GetGasTotalsTests(RailwayFixturesMixin, TestCase):
    def test_sums_available_weights_and_marks_incomplete(self):
        complete = self.make_tank(
            1001,
            gas_type='СПБТ',
            gas_weight=Decimal('32.02'),
            arrival_at=timezone.now(),
        )
        incomplete = self.make_tank(
            1002,
            gas_type='СПБТ',
            empty_weight=Decimal('22.96'),
            arrival_at=timezone.now(),
        )
        batch = self.make_batch(tanks=[complete, incomplete])

        totals = batch.get_gas_totals()

        self.assertTrue(totals['spbt']['has_tanks'])
        self.assertTrue(totals['spbt']['incomplete'])
        self.assertEqual(totals['spbt']['amount'], Decimal('32.02'))
        self.assertFalse(totals['pba']['has_tanks'])
        self.assertEqual(totals['pba']['amount'], Decimal('0'))

    def test_complete_tanks_are_not_marked_incomplete(self):
        spbt = self.make_tank(
            2001,
            gas_type='СПБТ',
            gas_weight=Decimal('10.50'),
            arrival_at=timezone.now(),
        )
        pba = self.make_tank(
            2002,
            gas_type='ПБА',
            gas_weight=Decimal('4.25'),
            arrival_at=timezone.now(),
        )
        batch = self.make_batch(tanks=[spbt, pba])

        totals = batch.get_gas_totals()

        self.assertEqual(totals['spbt']['amount'], Decimal('10.50'))
        self.assertFalse(totals['spbt']['incomplete'])
        self.assertEqual(totals['pba']['amount'], Decimal('4.25'))
        self.assertFalse(totals['pba']['incomplete'])

    def test_uses_latest_history_only(self):
        tank = self.make_tank(
            3001,
            gas_type='СПБТ',
            gas_weight=Decimal('10'),
            arrival_at=timezone.now() - timedelta(days=1),
        )
        RailwayTankHistory.objects.create(
            tank=tank,
            gas_type='СПБТ',
            gas_weight=Decimal('3'),
            arrival_at=timezone.now(),
        )
        batch = self.make_batch(tanks=[tank])

        self.assertEqual(batch.get_gas_totals()['spbt']['amount'], Decimal('3'))


class RailwayBatchDetailViewTests(RailwayFixturesMixin, TestCase):
    def test_shows_partial_sum_with_warning(self):
        complete = self.make_tank(
            4001,
            gas_type='СПБТ',
            gas_weight=Decimal('36.76'),
            arrival_at=timezone.now(),
        )
        missing = self.make_tank(
            4002,
            gas_type='СПБТ',
            empty_weight=Decimal('37.80'),
            arrival_at=timezone.now(),
        )
        batch = self.make_batch(tanks=[complete, missing])

        response = self.client.get(
            reverse('railway_service:railway_batch_detail', args=[batch.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '36.76')
        self.assertContains(response, 'text-danger')
        self.assertContains(
            response,
            'Данные получены не со всех цистерн, требуется уточнение',
        )
        self.assertContains(response, 'СПБТ газа')
        self.assertNotContains(response, 'ПБА газа')

    def test_hides_spbt_when_batch_has_only_pba(self):
        tank = self.make_tank(
            4003,
            gas_type='ПБА',
            gas_weight=Decimal('4.25'),
            arrival_at=timezone.now(),
        )
        batch = self.make_batch(tanks=[tank])

        response = self.client.get(
            reverse('railway_service:railway_batch_detail', args=[batch.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'ПБА газа')
        self.assertContains(response, '4.25')
        self.assertNotContains(response, 'СПБТ газа')

    def test_shows_both_types_when_batch_has_spbt_and_pba(self):
        spbt = self.make_tank(
            4004,
            gas_type='СПБТ',
            gas_weight=Decimal('10.50'),
            arrival_at=timezone.now(),
        )
        pba = self.make_tank(
            4005,
            gas_type='ПБА',
            gas_weight=Decimal('4.25'),
            arrival_at=timezone.now(),
        )
        batch = self.make_batch(tanks=[spbt, pba])

        response = self.client.get(
            reverse('railway_service:railway_batch_detail', args=[batch.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'СПБТ газа')
        self.assertContains(response, 'ПБА газа')
        self.assertContains(response, '10.50')
        self.assertContains(response, '4.25')
