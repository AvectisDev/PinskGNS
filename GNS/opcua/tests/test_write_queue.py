from unittest.mock import AsyncMock, patch

from asgiref.sync import async_to_sync
from asyncua import ua
from django.test import SimpleTestCase

from opcua.bridge import writer as opc_writer
from opcua.bridge.client import OpcBridgeClient
from opcua.bridge.dispatcher import TriggerDispatcher


class OpcWriteRetryTests(SimpleTestCase):
    @patch('opcua.bridge.writer.asyncio.sleep', new_callable=AsyncMock)
    def test_write_retries_then_succeeds(self, _sleep):
        bridge = AsyncMock()
        bridge.write_tag = AsyncMock(
            side_effect=[RuntimeError('Bad'), RuntimeError('Bad'), None],
        )

        async_to_sync(opc_writer._write_with_retries)(
            bridge,
            'railway.camera_worked',
            False,
        )

        self.assertEqual(bridge.write_tag.call_count, 3)

    @patch('opcua.bridge.writer.asyncio.sleep', new_callable=AsyncMock)
    def test_write_exhausted_raises(self, _sleep):
        bridge = AsyncMock()
        bridge.write_tag = AsyncMock(side_effect=RuntimeError('Bad'))

        with self.assertRaises(RuntimeError):
            async_to_sync(opc_writer._write_with_retries)(
                bridge,
                'autogas.stop_batch',
                True,
            )

        self.assertEqual(bridge.write_tag.call_count, opc_writer.WRITE_MAX_ATTEMPTS)


class OpcWriteEnqueueTests(SimpleTestCase):
    @patch('opcua.api._redis_client')
    def test_write_tag_enqueues_without_waiting(self, redis_factory):
        client = redis_factory.return_value

        from opcua.api import write_tag

        ok = write_tag('railway.camera_worked', False)

        self.assertTrue(ok)
        client.lpush.assert_called_once()
        client.blpop.assert_not_called()
        client.brpop.assert_not_called()


class OpcWriteDataValueTests(SimpleTestCase):
    def test_write_tag_sends_datavalue_without_source_timestamp(self):
        """Melsoft отклоняет SourceTimestamp → BadWriteNotSupported."""
        dispatcher = TriggerDispatcher()
        bridge = OpcBridgeClient(url='opc.tcp://example', dispatcher=dispatcher)
        node = AsyncMock()
        node.read_data_type_as_variant_type = AsyncMock(
            return_value=ua.VariantType.Boolean,
        )
        node.write_value = AsyncMock()
        bridge._nodes_by_name = {'railway.camera_worked': node}

        async_to_sync(bridge.write_tag)('railway.camera_worked', False)

        node.write_value.assert_called_once()
        datavalue = node.write_value.call_args.args[0]
        self.assertIsInstance(datavalue, ua.DataValue)
        self.assertIsNone(datavalue.SourceTimestamp)
        self.assertIsNone(datavalue.ServerTimestamp)
        self.assertFalse(datavalue.Value.Value)
        self.assertEqual(dispatcher.snapshot.get('railway.camera_worked'), False)
