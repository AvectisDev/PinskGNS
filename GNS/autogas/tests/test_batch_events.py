from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import TestCase

from autogas.batch_events import (
    process_autogas_batch_complete,
    process_autogas_batch_create,
)
from autogas.models import AutoGasBatch
from .helpers import AutoGasFixturesMixin


class AutoGasBatchEventTests(AutoGasFixturesMixin, TestCase):
    @patch('autogas.batch_events.write_tag')
    @patch('autogas.batch_events.get_transport_numbers')
    def test_empty_numbers_do_not_confirm_create(self, get_numbers, write_tag):
        get_numbers.return_value = []
        process_autogas_batch_create({
            'batch_type_code': 1,
            'gas_type': 2,
            'request_batch_create': True,
            'response_batch_create': False,
        })
        self.assertEqual(AutoGasBatch.objects.count(), 0)
        write_tag.assert_not_called()

    @patch('autogas.batch_events.write_tag')
    def test_unknown_gas_type_stops_batch(self, write_tag):
        process_autogas_batch_create({
            'batch_type_code': 1,
            'gas_type': 1,
            'request_batch_create': True,
            'response_batch_create': False,
        })
        self.assertEqual(AutoGasBatch.objects.count(), 0)
        write_tag.assert_called_once_with('autogas.stop_batch', True)

    @patch('autogas.batch_events.write_tag')
    @patch('autogas.batch_events.get_transport_numbers')
    def test_create_batch_success(self, get_numbers, write_tag):
        get_numbers.return_value = [self.truck.registration_number]
        process_autogas_batch_create({
            'batch_type_code': 1,
            'gas_type': 3,
            'request_batch_create': True,
            'response_batch_create': False,
        })
        batch = AutoGasBatch.objects.get()
        self.assertTrue(batch.is_active)
        self.assertEqual(batch.batch_type, 'l')
        self.assertEqual(batch.gas_type, 'ПБА')
        write_tag.assert_any_call('autogas.truck_capacity', Decimal('20000'))
        write_tag.assert_any_call('autogas.response_batch_create', True)

    @patch('autogas.batch_events.write_tag')
    @patch('autogas.batch_events.get_transport_numbers')
    def test_create_stops_when_active_exists(self, get_numbers, write_tag):
        self.make_batch(is_active=True)
        get_numbers.return_value = [self.tractor.registration_number]
        process_autogas_batch_create({
            'batch_type_code': 2,
            'gas_type': 2,
            'request_batch_create': True,
            'response_batch_create': False,
        })
        self.assertEqual(AutoGasBatch.objects.filter(is_active=True).count(), 1)
        write_tag.assert_called_with('autogas.stop_batch', True)

    @patch('autogas.batch_events.write_tag')
    def test_complete_batch(self, write_tag):
        batch = self.make_batch(is_active=True)
        process_autogas_batch_complete({
            'gas_amount': Decimal('12'),
            'truck_empty_weight': Decimal('1'),
            'truck_full_weight': Decimal('2'),
            'weight_gas_amount': Decimal('1'),
            'request_batch_complete': True,
            'response_batch_complete': False,
        })
        batch.refresh_from_db()
        self.assertFalse(batch.is_active)
        self.assertEqual(batch.gas_amount, Decimal('12'))
        write_tag.assert_called_once_with('autogas.response_batch_complete', True)

    @patch('autogas.batch_events.write_tag')
    def test_complete_without_active_does_not_ack(self, write_tag):
        process_autogas_batch_complete({
            'gas_amount': 1,
            'request_batch_complete': True,
            'response_batch_complete': False,
        })
        write_tag.assert_not_called()
