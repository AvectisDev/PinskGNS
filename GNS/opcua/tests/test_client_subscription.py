from unittest.mock import MagicMock, patch

from asgiref.sync import async_to_sync
from django.test import SimpleTestCase

from opcua.bridge.client import OpcBridgeClient
from opcua.bridge.dispatcher import TriggerDispatcher


class OpcDataChangeSkipTests(SimpleTestCase):
    def test_unchanged_value_skips_dispatcher(self):
        dispatcher = TriggerDispatcher()
        dispatcher.on_snapshot({'railway.stable_weight': 36.24})
        bridge = OpcBridgeClient(url='opc.tcp://example', dispatcher=dispatcher)
        bridge._name_by_nodeid = {'ns=4;s=weight': 'railway.stable_weight'}

        event = MagicMock()
        event.node = MagicMock()
        event.node.nodeid.to_string.return_value = 'ns=4;s=weight'
        event.value = 36.24

        with patch.object(dispatcher, 'on_snapshot') as on_snapshot:
            async_to_sync(bridge._on_data_change)(event)
            on_snapshot.assert_not_called()

    def test_changed_value_calls_dispatcher(self):
        dispatcher = TriggerDispatcher()
        dispatcher.on_snapshot({'railway.stable_weight': 0.0})
        bridge = OpcBridgeClient(url='opc.tcp://example', dispatcher=dispatcher)
        bridge._name_by_nodeid = {'ns=4;s=weight': 'railway.stable_weight'}

        event = MagicMock()
        event.node = MagicMock()
        event.node.nodeid.to_string.return_value = 'ns=4;s=weight'
        event.value = 36.24

        async_to_sync(bridge._on_data_change)(event)
        self.assertEqual(dispatcher.snapshot.get('railway.stable_weight'), 36.24)
