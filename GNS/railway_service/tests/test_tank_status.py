from unittest.mock import MagicMock, patch

from django.core.cache import cache
from django.test import SimpleTestCase, override_settings

from railway_service.management.commands.railway_tank import Command
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
