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
        node.read_data_value = AsyncMock(
            return_value=ua.DataValue(ua.Variant(False, ua.VariantType.Boolean)),
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

    def test_write_string_uses_live_string_variant(self):
        dispatcher = TriggerDispatcher()
        bridge = OpcBridgeClient(url='opc.tcp://example', dispatcher=dispatcher)
        node = AsyncMock()
        # Data type node может врать; живое значение — String.
        node.read_data_type_as_variant_type = AsyncMock(
            return_value=ua.VariantType.Byte,
        )
        node.read_data_value = AsyncMock(
            return_value=ua.DataValue(ua.Variant('', ua.VariantType.String)),
        )
        node.write_value = AsyncMock()
        bridge._nodes_by_name = {
            'autogas.vehicle_select.vehicle_list_0': node,
        }

        async_to_sync(bridge.write_tag)(
            'autogas.vehicle_select.vehicle_list_0',
            '1    AI0008-1',
        )

        datavalue = node.write_value.call_args.args[0]
        self.assertEqual(datavalue.Value.VariantType, ua.VariantType.String)
        self.assertEqual(datavalue.Value.Value, '1    AI0008-1')

    def test_write_empty_string_is_not_null(self):
        dispatcher = TriggerDispatcher()
        bridge = OpcBridgeClient(url='opc.tcp://example', dispatcher=dispatcher)
        node = AsyncMock()
        node.read_data_type_as_variant_type = AsyncMock(
            return_value=ua.VariantType.String,
        )
        node.read_data_value = AsyncMock(
            return_value=ua.DataValue(ua.Variant('x', ua.VariantType.String)),
        )
        node.write_value = AsyncMock()
        bridge._nodes_by_name = {
            'autogas.vehicle_select.proposed_truck_number': node,
        }

        async_to_sync(bridge.write_tag)(
            'autogas.vehicle_select.proposed_truck_number',
            '',
        )

        datavalue = node.write_value.call_args.args[0]
        self.assertEqual(datavalue.Value.VariantType, ua.VariantType.String)
        self.assertEqual(datavalue.Value.Value, '')

    def test_write_bytestring_pads_to_32(self):
        dispatcher = TriggerDispatcher()
        bridge = OpcBridgeClient(url='opc.tcp://example', dispatcher=dispatcher)
        node = AsyncMock()
        node.read_data_type_as_variant_type = AsyncMock(
            return_value=ua.VariantType.ByteString,
        )
        node.read_data_value = AsyncMock(
            return_value=ua.DataValue(
                ua.Variant(b'\x00' * 32, ua.VariantType.ByteString),
            ),
        )
        node.write_value = AsyncMock()
        bridge._nodes_by_name = {
            'autogas.vehicle_select.vehicle_list_0': node,
        }

        async_to_sync(bridge.write_tag)(
            'autogas.vehicle_select.vehicle_list_0',
            'AI0008-1',
        )

        datavalue = node.write_value.call_args.args[0]
        self.assertEqual(datavalue.Value.VariantType, ua.VariantType.ByteString)
        written = datavalue.Value.Value
        self.assertEqual(len(written), 32)
        self.assertTrue(written.startswith(b'AI0008-1'))
        self.assertTrue(written.endswith(b'\x00'))

    def test_write_byte_array_pads_to_32(self):
        """Melsoft STRING[32] иногда отдаёт VariantType.Byte + массив."""
        dispatcher = TriggerDispatcher()
        bridge = OpcBridgeClient(url='opc.tcp://example', dispatcher=dispatcher)
        node = AsyncMock()
        node.read_data_type_as_variant_type = AsyncMock(
            return_value=ua.VariantType.Byte,
        )
        node.read_data_value = AsyncMock(
            return_value=ua.DataValue(
                ua.Variant([0] * 32, ua.VariantType.Byte, is_array=True),
            ),
        )
        node.write_value = AsyncMock()
        bridge._nodes_by_name = {
            'autogas.vehicle_select.proposed_truck_number': node,
        }

        async_to_sync(bridge.write_tag)(
            'autogas.vehicle_select.proposed_truck_number',
            'AH0193-1',
        )

        datavalue = node.write_value.call_args.args[0]
        self.assertEqual(datavalue.Value.VariantType, ua.VariantType.Byte)
        written = bytes(datavalue.Value.Value)
        self.assertEqual(len(written), 32)
        self.assertTrue(written.startswith(b'AH0193-1'))
