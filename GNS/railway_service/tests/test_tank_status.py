from unittest.mock import MagicMock, patch

from django.core.cache import cache
from django.test import SimpleTestCase, override_settings
from opcua import ua

from railway_service.management.commands.railway_tank import (
    HANDLE_LOCK_KEY,
    OPC_READ_RETRIES,
    Command,
)
from railway_service.services.status_log import log_railway_tank_status


@override_settings(CACHES={
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'railway-tank-status-tests',
    }
})
class RailwayTankStatusLogTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    @patch('railway_service.services.status_log.logger')
    def test_status_logged_only_when_changed(self, logger):
        idle = 'tank_weight=35.38, camera_worked=False, is_on_station=False'
        log_railway_tank_status(idle)
        log_railway_tank_status(idle)
        logger.info.assert_called_once_with(idle)

        active = 'tank_weight=35.38, camera_worked=True, is_on_station=True'
        log_railway_tank_status(active)
        self.assertEqual(logger.info.call_count, 2)
        logger.info.assert_called_with(active)


@override_settings(CACHES={
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'railway-tank-handle-tests',
    }
})
class RailwayTankHandleLoggingTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        patcher = patch(
            'railway_service.management.commands.railway_tank.create_opc_client'
        )
        self.addCleanup(patcher.stop)
        patcher.start()
        disconnect_patcher = patch(
            'railway_service.management.commands.railway_tank.disconnect_opc'
        )
        self.addCleanup(disconnect_patcher.stop)
        disconnect_patcher.start()
        sleep_patcher = patch(
            'railway_service.management.commands.railway_tank.time.sleep'
        )
        self.addCleanup(sleep_patcher.stop)
        sleep_patcher.start()
        self.command = Command()
        self.command.get_opc_value = MagicMock(side_effect={
            'tank_weight': 35.38001251220703,
            'camera_worked': False,
            'is_on_station': False,
        }.get)

    def test_handle_logs_idle_status_once(self):
        with self.assertLogs('railway', level='INFO') as captured:
            self.command.handle()
            self.command.handle()
        status_logs = [line for line in captured.output if 'tank_weight=' in line]
        self.assertEqual(len(status_logs), 1)

    def test_handle_skips_when_opc_values_incomplete(self):
        self.command.get_opc_value = MagicMock(side_effect={
            'tank_weight': None,
            'camera_worked': None,
            'is_on_station': None,
        }.get)
        self.command.set_opc_value = MagicMock()

        with self.assertLogs('railway', level='WARNING') as captured:
            self.command.handle()

        self.assertTrue(
            any('Неполные OPC-значения' in line for line in captured.output)
        )
        self.command.set_opc_value.assert_not_called()
        self.assertIsNone(cache.get('railway_tank_processing'))

    def test_handle_skips_when_lock_held(self):
        cache.set(HANDLE_LOCK_KEY, True, timeout=30)
        self.command.client.connect = MagicMock()

        self.command.handle()

        self.command.client.connect.assert_not_called()


@override_settings(CACHES={
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'railway-tank-opc-tests',
    }
})
class RailwayTankOpcTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        patcher = patch(
            'railway_service.management.commands.railway_tank.create_opc_client'
        )
        self.addCleanup(patcher.stop)
        patcher.start()
        sleep_patcher = patch(
            'railway_service.management.commands.railway_tank.time.sleep'
        )
        self.addCleanup(sleep_patcher.stop)
        self.sleep = sleep_patcher.start()
        self.command = Command()
        self.node = MagicMock()
        self.command.client.get_node.return_value = self.node

    def test_get_opc_value_retries_then_succeeds(self):
        self.node.get_value.side_effect = [
            RuntimeError('The operation failed.(Bad)'),
            RuntimeError('The operation failed.(Bad)'),
            35.38,
        ]

        value = self.command.get_opc_value('tank_weight')

        self.assertEqual(value, 35.38)
        self.assertEqual(self.node.get_value.call_count, OPC_READ_RETRIES)
        self.assertEqual(self.sleep.call_count, OPC_READ_RETRIES - 1)

    def test_get_opc_value_returns_none_after_retries(self):
        self.node.get_value.side_effect = RuntimeError('The operation failed.(Bad)')

        with self.assertLogs('railway', level='ERROR') as captured:
            value = self.command.get_opc_value('tank_weight')

        self.assertIsNone(value)
        self.assertEqual(self.node.get_value.call_count, OPC_READ_RETRIES)
        self.assertTrue(any('tank_weight' in line for line in captured.output))

    def test_set_opc_value_writes_boolean_variant(self):
        self.node.get_data_type_as_variant_type.return_value = ua.VariantType.Boolean

        ok = self.command.set_opc_value('camera_worked', False)

        self.assertTrue(ok)
        self.node.set_value.assert_called_once_with(False, ua.VariantType.Boolean)
