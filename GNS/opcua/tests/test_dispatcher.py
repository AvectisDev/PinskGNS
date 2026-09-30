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
    def test_rising_edge_fires_railway_camera(self, current_app):
        idle = {
            'railway.stable_weight': 35.0,
            'railway.camera_worked': False,
            'railway.on_station': False,
            'railway.active': True,
            'railway.batch_type': 1,
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
    def test_railway_batch_start_and_end_edges(self, current_app):
        idle = {
            'railway.active': False,
            'railway.batch_type': 0,
        }
        self.dispatcher.on_snapshot(idle)
        current_app.send_task.assert_not_called()

        started = self.dispatcher.on_snapshot({
            'railway.active': True,
            'railway.batch_type': 1,
        })
        self.assertEqual(started, ['railway_batch_started'])
        self.assertEqual(
            current_app.send_task.call_args[0][0],
            'railway_service.tasks.process_railway_batch_started',
        )

        ended = self.dispatcher.on_snapshot({
            'railway.active': False,
            'railway.batch_type': 0,
        })
        self.assertEqual(ended, ['railway_batch_ended'])
        self.assertEqual(
            current_app.send_task.call_args[0][0],
            'railway_service.tasks.process_railway_batch_ended',
        )

    @patch('opcua.bridge.dispatcher.current_app')
    def test_no_refire_while_condition_active(self, current_app):
        snapshot = {
            'railway.stable_weight': 35.0,
            'railway.camera_worked': True,
            'railway.on_station': True,
            'railway.active': True,
            'railway.batch_type': 1,
        }
        # force_pending: active + camera → start и camera
        fired = self.dispatcher.on_snapshot(snapshot, force_pending=True)
        self.assertCountEqual(
            fired,
            ['railway_batch_started', 'railway_camera_worked'],
        )
        call_count = current_app.send_task.call_count
        self.dispatcher.on_snapshot(snapshot)
        self.assertEqual(current_app.send_task.call_count, call_count)

    @patch('opcua.bridge.dispatcher.current_app')
    def test_force_pending_autogas_create(self, current_app):
        snapshot = {
            'autogas.request_batch_create': True,
            'autogas.response_batch_create': False,
            'autogas.batch_type_code': 1,
            'autogas.gas_type': 2,
            'autogas.vehicle_select.proposed_ready': False,
            'autogas.vehicle_select.vehicle_list_0': '',
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
            'autogas.vehicle_select.vehicle_list_0': '',
        }
        fired = self.dispatcher.on_snapshot(snapshot, force_pending=True)
        self.assertNotIn('autogas_batch_create', fired)

    @patch('opcua.bridge.dispatcher.current_app')
    def test_autogas_create_skipped_when_vehicle_list_prepared(self, current_app):
        snapshot = {
            'autogas.request_batch_create': True,
            'autogas.response_batch_create': False,
            'autogas.batch_type_code': 1,
            'autogas.gas_type': 2,
            'autogas.vehicle_select.proposed_ready': False,
            'autogas.vehicle_select.vehicle_list_0': '1    1111AA-1',
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
        trigger = next(t for t in TRIGGERS if t.name == 'railway_camera_worked')
        payload = build_payload(trigger, {
            'railway.stable_weight': 10,
            'railway.camera_worked': True,
            'railway.on_station': False,
        })
        self.assertEqual(payload['stable_weight'], 10)
        self.assertTrue(payload['camera_worked'])
        self.assertFalse(payload['on_station'])

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
            'autogas.vehicle_select.vehicle_list_2': '3    2222BB-2    3333CC-3',
        })
        self.assertEqual(payload['list_mode'], True)
        self.assertEqual(payload['selected_vehicle_index'], 2)
        self.assertEqual(payload['batch_type_code'], 1)
        self.assertEqual(payload['vehicle_list_2'], '3    2222BB-2    3333CC-3')
