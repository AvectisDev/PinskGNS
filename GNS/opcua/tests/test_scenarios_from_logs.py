"""Интеграционные сценарии диспетчера по логам 13–20.10."""

from unittest.mock import patch

from django.core.cache import cache
from django.test import SimpleTestCase, override_settings

from opcua.bridge.dispatcher import TriggerDispatcher


@override_settings(CACHES={
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'opcua-log-scenarios',
    }
})
class LogScenarioDispatcherTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.dispatcher = TriggerDispatcher()

    @patch('opcua.bridge.dispatcher.current_app')
    def test_stuck_request_without_propose_ready_can_refire_create(self, current_app):
        """
        Stuck handshake: request=True, response=False, без proposed_ready/list —
        повторный фронт (после False) снова ставит create.
        """
        pending = {
            'autogas.request_batch_create': True,
            'autogas.response_batch_create': False,
            'autogas.batch_type_code': 1,
            'autogas.gas_type': 2,
            'autogas.vehicle_select.proposed_ready': False,
            'autogas.vehicle_select.vehicle_list_0': '',
        }
        self.dispatcher.on_snapshot({
            **pending,
            'autogas.request_batch_create': False,
        })
        first = self.dispatcher.on_snapshot(pending)
        self.assertIn('autogas_batch_create', first)

        # Условие остаётся True — повтор не жжём.
        again = self.dispatcher.on_snapshot(pending)
        self.assertEqual(again, [])

        # PLC сбросил и снова поднял request (Stop/Start).
        self.dispatcher.on_snapshot({
            **pending,
            'autogas.request_batch_create': False,
        })
        second = self.dispatcher.on_snapshot(pending)
        self.assertIn('autogas_batch_create', second)
        self.assertEqual(current_app.send_task.call_count, 2)

    @patch('opcua.bridge.dispatcher.current_app')
    def test_reconnect_active_with_type_starts_once(self, current_app):
        fired = self.dispatcher.on_snapshot(
            {
                'railway.active': True,
                'railway.batch_type': 2,
            },
            force_pending=True,
        )
        self.assertEqual(fired, ['railway_batch_started'])
        again = self.dispatcher.on_snapshot({
            'railway.active': True,
            'railway.batch_type': 2,
        })
        self.assertEqual(again, [])
        self.assertEqual(current_app.send_task.call_count, 1)

    @patch('opcua.bridge.dispatcher.current_app')
    def test_reconnect_inactive_ends_once(self, current_app):
        fired = self.dispatcher.on_snapshot(
            {'railway.active': False, 'railway.batch_type': 0},
            force_pending=True,
        )
        self.assertEqual(fired, ['railway_batch_ended'])
        again = self.dispatcher.on_snapshot(
            {'railway.active': False, 'railway.batch_type': 0},
        )
        self.assertEqual(again, [])
