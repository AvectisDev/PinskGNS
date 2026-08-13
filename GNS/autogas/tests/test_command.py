from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import TestCase

from autogas.management.commands.auto_gas_batch import Command
from autogas.models import AutoGasBatch
from .helpers import AutoGasFixturesMixin


class AutoGasCommandTests(AutoGasFixturesMixin, TestCase):
    def setUp(self):
        super().setUp()
        patcher = patch(
            'autogas.management.commands.auto_gas_batch.create_opc_client'
        )
        self.addCleanup(patcher.stop)
        patcher.start()
        self.command = Command()
        self.command.set_opc_value = MagicMock()

    def test_empty_numbers_do_not_confirm_create(self):
        self.command.get_transport_numbers = MagicMock(return_value=[])
        self.command.create_batch(1, 2)
        self.assertEqual(AutoGasBatch.objects.count(), 0)
        self.command.set_opc_value.assert_not_called()

    def test_unknown_gas_type_stops_batch(self):
        self.command.create_batch(1, 1)
        self.assertEqual(AutoGasBatch.objects.count(), 0)
        self.command.set_opc_value.assert_called_once_with('stop_batch', True)

    def test_create_batch_success(self):
        self.command.get_transport_numbers = MagicMock(
            return_value=[self.truck.registration_number]
        )
        self.command.create_batch(1, 3)
        batch = AutoGasBatch.objects.get()
        self.assertTrue(batch.is_active)
        self.assertEqual(batch.batch_type, 'l')
        self.assertEqual(batch.gas_type, 'ПБА')
        self.command.set_opc_value.assert_any_call(
            'truck_capacity',
            Decimal('20000'),
        )
        self.command.set_opc_value.assert_any_call('response_batch_create', True)

    def test_create_stops_when_active_exists(self):
        self.make_batch(is_active=True)
        self.command.get_transport_numbers = MagicMock(
            return_value=[self.tractor.registration_number]
        )
        self.command.create_batch(2, 2)
        self.assertEqual(AutoGasBatch.objects.filter(is_active=True).count(), 1)
        self.command.set_opc_value.assert_called_with('stop_batch', True)

    def test_complete_batch(self):
        batch = self.make_batch(is_active=True)
        self.command.complete_batch({
            'gas_amount': Decimal('12'),
            'truck_empty_weight': Decimal('1'),
            'truck_full_weight': Decimal('2'),
            'weight_gas_amount': Decimal('1'),
        })
        batch.refresh_from_db()
        self.assertFalse(batch.is_active)
        self.assertEqual(batch.gas_amount, Decimal('12'))
        self.command.set_opc_value.assert_called_once_with(
            'response_batch_complete',
            True,
        )

    def test_complete_without_active_does_not_ack(self):
        self.command.complete_batch({'gas_amount': 1})
        self.command.set_opc_value.assert_not_called()
