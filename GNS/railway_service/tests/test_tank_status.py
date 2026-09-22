from unittest.mock import MagicMock, patch

from django.core.cache import cache
from django.test import SimpleTestCase, override_settings

from railway_service.services.status_log import log_railway_tank_status
from railway_service.services.tank_events import process_railway_tank_event


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
        'LOCATION': 'railway-tank-event-tests',
    }
})
class RailwayTankEventTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    @patch('railway_service.services.tank_events.write_tag')
    @patch('railway_service.services.tank_events.fetch_railway_tank_data')
    @patch('railway_service.services.tank_events.time.sleep')
    def test_skips_when_opc_incomplete(self, _sleep, fetch_data, write_tag):
        process_railway_tank_event({
            'tank_weight': None,
            'camera_worked': True,
            'is_on_station': True,
        })
        fetch_data.assert_not_called()
        write_tag.assert_not_called()

    @patch('railway_service.services.tank_events.batch_process')
    @patch('railway_service.services.tank_events.tank_process')
    @patch('railway_service.services.tank_events.write_tag')
    @patch('railway_service.services.tank_events.fetch_railway_tank_data')
    @patch('railway_service.services.tank_events.time.sleep')
    def test_processes_camera_event(
        self,
        _sleep,
        fetch_data,
        write_tag,
        tank_process,
        batch_process,
    ):
        fetch_data.return_value = (12345678, b'img')
        tank = MagicMock()
        tank_process.return_value = tank

        process_railway_tank_event({
            'tank_weight': 35.38,
            'camera_worked': True,
            'is_on_station': True,
        })

        write_tag.assert_called_once_with('railway.camera_worked', False)
        tank_process.assert_called_once()
        batch_process.assert_called_once_with(tank)
