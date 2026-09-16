from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.core.cache import cache
from django.test import SimpleTestCase, TestCase, override_settings
from opcua import ua

from autogas.management.commands.auto_gas_batch import Command, convert_value_for_opc
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


class ConvertOpcValueTests(SimpleTestCase):
    def test_decimal_capacity_matches_float_node(self):
        converted = convert_value_for_opc(Decimal('4500.00'), ua.VariantType.Float)
        self.assertEqual(converted, 4500.0)
        self.assertIsInstance(converted, float)

    def test_decimal_capacity_matches_int32_node(self):
        converted = convert_value_for_opc(Decimal('4500.00'), ua.VariantType.Int32)
        self.assertEqual(converted, 4500)
        self.assertIsInstance(converted, int)

    def test_bool_stays_bool(self):
        self.assertIs(convert_value_for_opc(1, ua.VariantType.Boolean), True)


class AutoGasOpcWriteTests(SimpleTestCase):
    def setUp(self):
        patcher = patch(
            'autogas.management.commands.auto_gas_batch.create_opc_client'
        )
        self.addCleanup(patcher.stop)
        patcher.start()
        self.command = Command()
        self.node = MagicMock()
        self.command.client.get_node.return_value = self.node

    def test_set_opc_value_writes_float_variant(self):
        self.node.get_data_type_as_variant_type.return_value = ua.VariantType.Float
        self.command.set_opc_value('truck_capacity', Decimal('4500.00'))
        self.node.set_value.assert_called_once_with(4500.0, ua.VariantType.Float)

    def test_set_opc_value_falls_back_to_current_variant_type(self):
        self.node.get_data_type_as_variant_type.side_effect = RuntimeError('no datatype')
        self.node.get_data_value.return_value.Value.VariantType = ua.VariantType.Int32
        self.command.set_opc_value('truck_capacity', Decimal('4500.00'))
        self.node.set_value.assert_called_once_with(4500, ua.VariantType.Int32)


@override_settings(CACHES={
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'autogas-handle-log-tests',
    }
})
class AutoGasHandleLoggingTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        patcher = patch(
            'autogas.management.commands.auto_gas_batch.create_opc_client'
        )
        self.addCleanup(patcher.stop)
        patcher.start()
        disconnect_patcher = patch(
            'autogas.management.commands.auto_gas_batch.disconnect_opc'
        )
        self.addCleanup(disconnect_patcher.stop)
        disconnect_patcher.start()
        self.command = Command()
        idle = {key: False for key in Command.OPC_NODE_PATHS}
        idle['batch_type_code'] = 2
        idle['gas_type'] = 2
        self.command.get_opc_value = MagicMock(side_effect=lambda key: idle[key])

    def test_handle_logs_idle_status_once(self):
        with self.assertLogs('autogas', level='DEBUG') as captured:
            self.command.handle()
            self.command.handle()
        status_logs = [line for line in captured.output if 'Тип партии=' in line]
        self.assertEqual(len(status_logs), 1)
