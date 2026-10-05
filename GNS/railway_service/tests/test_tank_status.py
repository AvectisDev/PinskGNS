from unittest.mock import MagicMock, patch

from django.core.cache import cache
from django.test import SimpleTestCase, TestCase, override_settings

from railway_service.models import RailwayBatch
from railway_service.services.batch_events import (
    process_railway_batch_ended,
    process_railway_batch_started,
)
from railway_service.services.status_log import log_railway_tank_status
from railway_service.services.tank_events import batch_process, process_railway_tank_event
from railway_service.tests.helpers import RailwayFixturesMixin


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
        idle = 'stable_weight=35.38, camera_worked=False, on_station=False'
        log_railway_tank_status(idle)
        log_railway_tank_status(idle)
        logger.info.assert_called_once_with(idle)

        active = 'stable_weight=35.38, camera_worked=True, on_station=True'
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
            'stable_weight': None,
            'camera_worked': True,
            'on_station': True,
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
        batch_process_mock,
    ):
        fetch_data.return_value = (12345678, b'img')
        tank = MagicMock()
        tank_process.return_value = tank

        process_railway_tank_event({
            'stable_weight': 35.38,
            'camera_worked': True,
            'on_station': True,
        })

        write_tag.assert_called_once_with('railway.camera_worked', False)
        tank_process.assert_called_once()
        batch_process_mock.assert_called_once_with(tank)


class RailwayBatchEventTests(RailwayFixturesMixin, TestCase):
    def test_started_creates_batch_with_type(self):
        process_railway_batch_started({'active': True, 'batch_type': 1})
        batch = RailwayBatch.objects.get()
        self.assertTrue(batch.is_active)
        self.assertEqual(batch.batch_type, RailwayBatch.BatchType.LOADING)

    def test_started_does_not_duplicate_active(self):
        first = RailwayBatch.objects.create(is_active=True, batch_type=2)
        process_railway_batch_started({'active': True, 'batch_type': 1})
        self.assertEqual(RailwayBatch.objects.filter(is_active=True).count(), 1)
        first.refresh_from_db()
        self.assertEqual(first.batch_type, RailwayBatch.BatchType.UNLOADING)

    def test_started_updates_unknown_type(self):
        batch = RailwayBatch.objects.create(
            is_active=True,
            batch_type=RailwayBatch.BatchType.UNKNOWN,
        )
        process_railway_batch_started({'active': True, 'batch_type': 2})
        batch.refresh_from_db()
        self.assertEqual(batch.batch_type, RailwayBatch.BatchType.UNLOADING)

    def test_ended_closes_active_batch(self):
        batch = RailwayBatch.objects.create(is_active=True, batch_type=1)
        process_railway_batch_ended({'active': False})
        batch.refresh_from_db()
        self.assertFalse(batch.is_active)
        self.assertIsNotNone(batch.completed_at)

    def test_batch_process_adds_to_active_only(self):
        tank = self.make_tank(registration_number=111111)
        batch_process(tank)
        self.assertEqual(RailwayBatch.objects.count(), 0)

        batch = RailwayBatch.objects.create(is_active=True, batch_type=1)
        batch_process(tank)
        self.assertIn(tank, batch.railway_tank_list.all())
