from unittest.mock import patch

from django.core.cache import cache
from django.test import SimpleTestCase, override_settings

from opcua.bridge.dispatcher import TriggerDispatcher
from opcua.triggers import TRIGGERS, build_payload


@override_settings(CACHES={
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'opcua-dispatcher-tests',
    }
})
class TriggerDispatcherTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.dispatcher = TriggerDispatcher()

    @patch('opcua.bridge.dispatcher.current_app')
    def test_rising_edge_fires_railway(self, current_app):
        idle = {
            'railway.tank_weight': 35.0,
            'railway.camera_worked': False,
            'railway.is_on_station': False,
        }
        self.dispatcher.on_snapshot(idle)
        current_app.send_task.assert_not_called()

        fired = self.dispatcher.on_snapshot({
            **idle,
            'railway.camera_worked': True,
        })
        self.assertEqual(fired, ['railway_camera_worked'])
        current_app.send_task.assert_called_once()
        self.assertEqual(
            current_app.send_task.call_args[0][0],
            'railway_service.tasks.process_railway_tank_event',
        )

    @patch('opcua.bridge.dispatcher.current_app')
    def test_no_refire_while_condition_active(self, current_app):
        snapshot = {
            'railway.tank_weight': 35.0,
            'railway.camera_worked': True,
            'railway.is_on_station': True,
        }
        self.dispatcher.on_snapshot(snapshot, force_pending=True)
        self.assertEqual(current_app.send_task.call_count, 1)
        self.dispatcher.on_snapshot(snapshot)
        self.assertEqual(current_app.send_task.call_count, 1)

    @patch('opcua.bridge.dispatcher.current_app')
    def test_force_pending_autogas_create(self, current_app):
        snapshot = {
            'autogas.request_batch_create': True,
            'autogas.response_batch_create': False,
            'autogas.batch_type_code': 1,
            'autogas.gas_type': 2,
        }
        fired = self.dispatcher.on_snapshot(snapshot, force_pending=True)
        self.assertIn('autogas_batch_create', fired)

    def test_build_payload_strips_domain_prefix(self):
        trigger = TRIGGERS[0]
        payload = build_payload(trigger, {
            'railway.tank_weight': 10,
            'railway.camera_worked': True,
            'railway.is_on_station': False,
        })
        self.assertEqual(payload['tank_weight'], 10)
        self.assertTrue(payload['camera_worked'])
        self.assertFalse(payload['is_on_station'])
