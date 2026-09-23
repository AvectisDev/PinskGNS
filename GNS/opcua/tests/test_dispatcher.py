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
            'autogas.vehicle_select.proposed_ready': False,
            'autogas.vehicle_select.list_mode': False,
        }
        fired = self.dispatcher.on_snapshot(snapshot, force_pending=True)
        self.assertIn('autogas_batch_create', fired)

    @patch('opcua.bridge.dispatcher.current_app')
    def test_autogas_create_skipped_when_propose_ready(self, current_app):
        snapshot = {
            'autogas.request_batch_create': True,
            'autogas.response_batch_create': False,
            'autogas.batch_type_code': 1,
            'autogas.gas_type': 2,
            'autogas.vehicle_select.proposed_ready': True,
            'autogas.vehicle_select.list_mode': False,
        }
        fired = self.dispatcher.on_snapshot(snapshot, force_pending=True)
        self.assertNotIn('autogas_batch_create', fired)

    @patch('opcua.bridge.dispatcher.current_app')
    def test_operator_confirm_fires(self, current_app):
        snapshot = {
            'autogas.request_batch_create': True,
            'autogas.response_batch_create': False,
            'autogas.batch_type_code': 1,
            'autogas.gas_type': 2,
            'autogas.vehicle_select.operator_confirm': True,
            'autogas.vehicle_select.list_mode': False,
            'autogas.vehicle_select.proposed_ready': True,
            'autogas.vehicle_select.proposed_truck_number': '1111AA-1',
            'autogas.vehicle_select.proposed_trailer_number': '',
            'autogas.vehicle_select.selected_vehicle_index': -1,
        }
        fired = self.dispatcher.on_snapshot(snapshot, force_pending=True)
        self.assertIn('autogas_operator_confirm', fired)
        self.assertEqual(
            current_app.send_task.call_args[0][0],
            'autogas.tasks.process_autogas_operator_confirm',
        )

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

    def test_build_payload_vehicle_select_short_keys(self):
        trigger = next(t for t in TRIGGERS if t.name == 'autogas_operator_confirm')
        payload = build_payload(trigger, {
            'autogas.batch_type_code': 1,
            'autogas.gas_type': 2,
            'autogas.request_batch_create': True,
            'autogas.response_batch_create': False,
            'autogas.vehicle_select.list_mode': True,
            'autogas.vehicle_select.proposed_ready': False,
            'autogas.vehicle_select.proposed_truck_number': '',
            'autogas.vehicle_select.proposed_trailer_number': '',
            'autogas.vehicle_select.selected_vehicle_index': 2,
            'autogas.vehicle_select.operator_confirm': True,
        })
        self.assertEqual(payload['list_mode'], True)
        self.assertEqual(payload['selected_vehicle_index'], 2)
        self.assertEqual(payload['batch_type_code'], 1)
