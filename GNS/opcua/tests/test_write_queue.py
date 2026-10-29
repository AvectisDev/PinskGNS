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

    @patch('opcua.api.time.sleep')
    @patch('opcua.api._redis_client')
    def test_write_tag_wait_success(self, redis_factory, _sleep):
        client = redis_factory.return_value
        client.get.return_value = '{"ok": true}'

        from opcua.api import write_tag_wait

        ok = write_tag_wait('autogas.vehicle_select.proposed_truck_number', 'AI0008-1')

        self.assertTrue(ok)
        client.lpush.assert_called_once()
        payload = client.lpush.call_args.args[1]
        self.assertIn('reply_to', payload)
        client.get.assert_called()
        client.delete.assert_called()

    @patch('opcua.api.WRITE_WAIT_TIMEOUT_SECONDS', 0.01)
    @patch('opcua.api.WRITE_WAIT_POLL_SECONDS', 0.001)
    @patch('opcua.api.time.sleep')
    @patch('opcua.api._redis_client')
    def test_write_tag_wait_timeout(self, redis_factory, _sleep):
        client = redis_factory.return_value
        client.get.return_value = None

        from opcua.api import write_tag_wait

        ok = write_tag_wait(
            'autogas.vehicle_select.proposed_truck_number',
            'AI0008-1',
            timeout=0.01,
        )

        self.assertFalse(ok)

    @patch('opcua.api.write_tag_wait')
    def test_write_tags_wait_stops_on_first_fail(self, write_tag_wait):
        write_tag_wait.side_effect = [True, False]

        from opcua.api import write_tags_wait

        ok = write_tags_wait({
            'autogas.vehicle_select.proposed_truck_number': 'A',
            'autogas.vehicle_select.proposed_trailer_number': 'B',
            'autogas.vehicle_select.vehicle_list_0': '',
        })

        self.assertFalse(ok)
        self.assertEqual(write_tag_wait.call_count, 2)

    @patch('opcua.api._redis_client')
    def test_enqueue_unknown_tag(self, redis_factory):
        from opcua.api import write_tag

        self.assertFalse(write_tag('unknown.tag', 1))
        redis_factory.return_value.lpush.assert_not_called()


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

    def test_string_badtypemismatch_retries_bytestring(self):
        """Прод 19.10: live String → BadTypeMismatch → ByteString OK."""
        dispatcher = TriggerDispatcher()
        bridge = OpcBridgeClient(url='opc.tcp://example', dispatcher=dispatcher)
        node = AsyncMock()
        node.read_data_type_as_variant_type = AsyncMock(
            return_value=ua.VariantType.String,
        )
        node.read_data_value = AsyncMock(
            return_value=ua.DataValue(ua.Variant('', ua.VariantType.String)),
        )
        node.write_value = AsyncMock(
            side_effect=[
                RuntimeError('BadTypeMismatch'),
                None,
            ],
        )
        bridge._nodes_by_name = {
            'autogas.vehicle_select.proposed_truck_number': node,
        }

        async_to_sync(bridge.write_tag)(
            'autogas.vehicle_select.proposed_truck_number',
            'AH0193-1',
        )

        self.assertEqual(node.write_value.call_count, 2)
        first = node.write_value.call_args_list[0].args[0]
        second = node.write_value.call_args_list[1].args[0]
        self.assertEqual(first.Value.VariantType, ua.VariantType.String)
        self.assertEqual(second.Value.VariantType, ua.VariantType.ByteString)
        self.assertEqual(
            bridge._string_encoding_by_tag['autogas.vehicle_select.proposed_truck_number'],
            'bytestring',
        )

    def test_string_badtypemismatch_retries_byte_array(self):
        dispatcher = TriggerDispatcher()
        bridge = OpcBridgeClient(url='opc.tcp://example', dispatcher=dispatcher)
        node = AsyncMock()
        node.read_data_type_as_variant_type = AsyncMock(
            return_value=ua.VariantType.String,
        )
        node.read_data_value = AsyncMock(
            return_value=ua.DataValue(ua.Variant('', ua.VariantType.String)),
        )
        node.write_value = AsyncMock(
            side_effect=[
                RuntimeError('BadTypeMismatch'),
                RuntimeError('BadTypeMismatch'),
                None,
            ],
        )
        bridge._nodes_by_name = {
            'autogas.vehicle_select.vehicle_list_0': node,
        }

        async_to_sync(bridge.write_tag)(
            'autogas.vehicle_select.vehicle_list_0',
            '1    AI0008-1',
        )

        third = node.write_value.call_args_list[2].args[0]
        self.assertEqual(third.Value.VariantType, ua.VariantType.Byte)
        self.assertEqual(len(third.Value.Value), 32)
        self.assertEqual(
            bridge._string_encoding_by_tag['autogas.vehicle_select.vehicle_list_0'],
            'byte_array',
        )

    def test_string_encoding_cached_after_success(self):
        dispatcher = TriggerDispatcher()
        bridge = OpcBridgeClient(url='opc.tcp://example', dispatcher=dispatcher)
        node = AsyncMock()
        node.read_data_type_as_variant_type = AsyncMock(
            return_value=ua.VariantType.String,
        )
        node.read_data_value = AsyncMock(
            return_value=ua.DataValue(ua.Variant('', ua.VariantType.String)),
        )
        node.write_value = AsyncMock(
            side_effect=[RuntimeError('BadTypeMismatch'), None, None],
        )
        tag = 'autogas.vehicle_select.proposed_trailer_number'
        bridge._nodes_by_name = {tag: node}

        async_to_sync(bridge.write_tag)(tag, 'A0608A-1')
        async_to_sync(bridge.write_tag)(tag, 'A0000A-1')

        # Первый цикл: String fail + ByteString ok; второй — сразу ByteString.
        self.assertEqual(node.write_value.call_count, 3)
        last = node.write_value.call_args_list[2].args[0]
        self.assertEqual(last.Value.VariantType, ua.VariantType.ByteString)
        node.read_data_value.assert_called_once()

    def test_boolean_write_does_not_use_string_fallback(self):
        dispatcher = TriggerDispatcher()
        bridge = OpcBridgeClient(url='opc.tcp://example', dispatcher=dispatcher)
        node = AsyncMock()
        node.read_data_type_as_variant_type = AsyncMock(
            return_value=ua.VariantType.Boolean,
        )
        node.read_data_value = AsyncMock(
            return_value=ua.DataValue(ua.Variant(False, ua.VariantType.Boolean)),
        )
        node.write_value = AsyncMock(side_effect=RuntimeError('BadTypeMismatch'))
        bridge._nodes_by_name = {'autogas.vehicle_select.proposed_ready': node}

        with self.assertRaises(RuntimeError):
            async_to_sync(bridge.write_tag)(
                'autogas.vehicle_select.proposed_ready',
                True,
            )

        node.write_value.assert_called_once()
        self.assertEqual(bridge._string_encoding_by_tag, {})

    def test_string_all_encodings_fail_raises(self):
        dispatcher = TriggerDispatcher()
        bridge = OpcBridgeClient(url='opc.tcp://example', dispatcher=dispatcher)
        node = AsyncMock()
        node.read_data_type_as_variant_type = AsyncMock(
            return_value=ua.VariantType.String,
        )
        node.read_data_value = AsyncMock(
            return_value=ua.DataValue(ua.Variant('', ua.VariantType.String)),
        )
        node.write_value = AsyncMock(side_effect=RuntimeError('BadTypeMismatch'))
        bridge._nodes_by_name = {
            'autogas.vehicle_select.vehicle_list_1': node,
        }

        with self.assertRaises(RuntimeError):
            async_to_sync(bridge.write_tag)(
                'autogas.vehicle_select.vehicle_list_1',
                'x',
            )

        self.assertEqual(node.write_value.call_count, 3)

    def test_write_uint16_word_array(self):
        """SU2 vehicle_select: ARRAY [0..16] OF WORD → UInt16[17]."""
        from opcua.melsoft_words import pack_melsoft_string

        dispatcher = TriggerDispatcher()
        bridge = OpcBridgeClient(url='opc.tcp://example', dispatcher=dispatcher)
        node = AsyncMock()
        node.read_data_type_as_variant_type = AsyncMock(
            return_value=ua.VariantType.UInt16,
        )
        node.read_data_value = AsyncMock(
            return_value=ua.DataValue(
                ua.Variant([0] * 17, ua.VariantType.UInt16, is_array=True),
            ),
        )
        node.write_value = AsyncMock()
        bridge._nodes_by_name = {
            'autogas.vehicle_select.proposed_truck_number': node,
        }

        words = pack_melsoft_string('A 7583-1')
        async_to_sync(bridge.write_tag)(
            'autogas.vehicle_select.proposed_truck_number',
            words,
        )

        datavalue = node.write_value.call_args.args[0]
        self.assertEqual(datavalue.Value.VariantType, ua.VariantType.UInt16)
        self.assertEqual(list(datavalue.Value.Value)[:4], [8257, 13623, 13112, 12589])
        self.assertEqual(len(datavalue.Value.Value), 17)
