from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase
from unittest.mock import MagicMock, patch
import socket

from .models import Carousel
from .listener import cache, processing, protocol, transport
from .services import (
    CarouselPostNotFoundError,
    UnsupportedCarouselRequestError,
    process_carousel_data,
)
from .validation import is_value_in_range


class RangeValidationTests(SimpleTestCase):
    def test_value_inside_range(self):
        self.assertTrue(is_value_in_range(18.0, 17.0, 19.0))

    def test_value_outside_range(self):
        self.assertFalse(is_value_in_range(16.0, 17.0, 19.0))
        self.assertFalse(is_value_in_range(20.0, 17.0, 19.0))


class TcpFrameAssemblyTests(SimpleTestCase):
    def test_recv_exact_assembles_fragments(self):
        frame = bytes.fromhex('7A141036B0000D53')
        sock = MagicMock()
        sock.recv.side_effect = [frame[:3], frame[3:5], frame[5:]]

        result = transport.recv_exact(sock, 8)

        self.assertEqual(result, frame)
        self.assertEqual(sock.recv.call_count, 3)

    def test_recv_exact_raises_when_connection_closed(self):
        sock = MagicMock()
        sock.recv.side_effect = [b'\x7A\x14', b'']

        with self.assertRaises(ConnectionError):
            transport.recv_exact(sock, 8)

    @patch('carousel.listener.transport.socket.create_connection')
    def test_tcp_transport_assembles_fragments_across_timeout(
        self,
        create_connection,
    ):
        frame = bytes.fromhex('7A141036B0000D53')
        sock = MagicMock()
        sock.recv.side_effect = [
            frame[:2],
            socket.timeout,
            frame[2:],
        ]
        create_connection.return_value = sock

        tcp_transport = transport.TcpTransport('127.0.0.1', 4001, 1.0)

        self.assertEqual(tcp_transport.read_frame(8), b'')
        self.assertEqual(tcp_transport.read_frame(8), frame)

    @patch('carousel.listener.transport.socket.create_connection')
    def test_tcp_transport_write_uses_sendall(self, create_connection):
        sock = MagicMock()
        create_connection.return_value = sock
        tcp_transport = transport.TcpTransport('127.0.0.1', 4001, 1.0)

        payload = bytes.fromhex('5A14FFA410FF7D88')
        tcp_transport.write(payload)

        sock.sendall.assert_called_once_with(payload)

    @patch('carousel.listener.transport.time.monotonic')
    @patch('carousel.listener.transport.socket.create_connection')
    def test_stale_partial_buffer_raises_and_clears_buffer(
        self,
        create_connection,
        monotonic,
    ):
        sock = MagicMock()
        sock.recv.side_effect = [b'\xC2\x9B', socket.timeout, socket.timeout]
        create_connection.return_value = sock
        monotonic.side_effect = [0.0, 0.0, 11.0]

        tcp_transport = transport.TcpTransport('127.0.0.1', 4001, 1.0)

        self.assertEqual(tcp_transport.read_frame(8), b'')
        with self.assertRaises(transport.PartialBufferStaleError):
            tcp_transport.read_frame(8)
        self.assertEqual(tcp_transport._buffer, bytearray())


class CarouselRequestProcessingTests(SimpleTestCase):
    def setUp(self):
        cache.recent_requests.clear()

    def test_duplicate_request_reuses_response_from_memory(self):
        found, response = cache.get_cached_request(
            '0x7a', 1, 18000
        )
        self.assertFalse(found)
        self.assertIsNone(response)

        cache.cache_request_result(
            '0x7a', 1, 18000, b'response'
        )
        found, response = cache.get_cached_request(
            '0x7a', 1, 18000
        )
        self.assertTrue(found)
        self.assertEqual(response, b'response')

    def test_crc_matches_protocol_examples(self):
        examples = (
            '7A141036B0000D53',
            '701410ABE0029FC4',
            '5A14FFA410FF7D88',
            '5014FFA410FFFB8A',
        )

        for frame_hex in examples:
            with self.subTest(frame=frame_hex):
                valid, received, calculated = (
                    protocol.validate_frame_crc(
                        bytes.fromhex(frame_hex)
                    )
                )
                self.assertTrue(valid)
                self.assertEqual(received, calculated)

    def test_response_packet_matches_protocol_example(self):
        response = protocol.build_response_packet(
            request_type=0x7A,
            post_number=20,
            full_weight=42000,
        )
        self.assertEqual(response.hex().upper(), '5A14FFA410FF7D88')

    @patch.object(processing, 'get_and_remove_last_balloon')
    @patch.object(processing, 'check_settings')
    def test_read_only_saves_data_without_response(
        self,
        check_settings,
        get_balloon,
    ):
        get_balloon.return_value = ({
            'nfc_tag': 'test-tag',
            'serial_number': '123',
            'netto': 18.0,
            'brutto': 39.0,
            'filling_status': True,
        }, True)
        check_settings.return_value = processing.PostSettings(
            available=True,
            read_only=True,
            weight_correction=0.0,
            min_balloon_weight_from=17.0,
            min_balloon_weight_to=19.0,
            max_balloon_weight_from=35.0,
            max_balloon_weight_to=47.0,
            passport_weight_diff_from=0.0,
            passport_weight_diff_to=22.0,
        )

        response_required, full_weight, data = (
            processing.request_processing('0x7a', 1, 18500)
        )

        self.assertFalse(response_required)
        self.assertEqual(full_weight, 0)
        self.assertEqual(data['nfc_tag'], 'test-tag')
        self.assertEqual(data['empty_weight'], 18.5)

    @patch.object(processing, 'get_and_remove_last_balloon')
    @patch.object(processing, 'check_settings')
    def test_active_mode_returns_corrected_passport_weight(
        self,
        check_settings,
        get_balloon,
    ):
        get_balloon.return_value = ({
            'nfc_tag': 'test-tag',
            'serial_number': '123',
            'netto': 18.0,
            'brutto': 39.0,
            'filling_status': True,
        }, True)
        check_settings.return_value = processing.PostSettings(
            available=True,
            read_only=False,
            weight_correction=0.2,
            min_balloon_weight_from=17.0,
            min_balloon_weight_to=19.0,
            max_balloon_weight_from=35.0,
            max_balloon_weight_to=47.0,
            passport_weight_diff_from=0.0,
            passport_weight_diff_to=22.0,
        )

        response_required, full_weight, _ = (
            processing.request_processing('0x7a', 1, 18500)
        )

        self.assertTrue(response_required)
        self.assertEqual(full_weight, 39200)

    @patch.object(processing, 'record_post_error')
    @patch.object(processing, 'get_and_remove_last_balloon')
    @patch.object(processing, 'check_settings')
    def test_missing_settings_fails_safely(
        self,
        check_settings,
        get_balloon,
        record_error,
    ):
        get_balloon.return_value = ({
            'netto': 18.0,
            'brutto': 39.0,
            'filling_status': True,
        }, True)
        check_settings.return_value = processing.PostSettings(
            available=False,
            read_only=True,
            weight_correction=0.0,
            min_balloon_weight_from=None,
            min_balloon_weight_to=None,
            max_balloon_weight_from=None,
            max_balloon_weight_to=None,
            passport_weight_diff_from=None,
            passport_weight_diff_to=None,
        )

        response_required, full_weight, _ = (
            processing.request_processing('0x7a', 1, 18500)
        )

        self.assertFalse(response_required)
        self.assertEqual(full_weight, 0)
        record_error.assert_called_once()


class ProcessCarouselDataTests(TestCase):
    def test_request_0x7a_creates_carousel_record(self):
        carousel_post = process_carousel_data({
            'request_type': '0x7a',
            'carousel_number': 1,
            'post_number': 7,
            'is_empty': True,
            'empty_weight': 18.2,
            'nfc_tag': 'test-tag',
            'serial_number': '123',
            'size': 50,
            'netto': 18.0,
            'brutto': 39.0,
            'filling_status': True,
        })

        self.assertEqual(Carousel.objects.count(), 1)
        self.assertEqual(carousel_post.post_number, 7)
        self.assertEqual(carousel_post.nfc_tag, 'test-tag')
        self.assertTrue(carousel_post.is_empty)

    def test_request_0x70_updates_latest_post_record(self):
        old_post = Carousel.objects.create(
            post_number=3,
            is_empty=True,
            full_weight=None,
        )
        latest_post = Carousel.objects.create(
            post_number=3,
            is_empty=True,
            full_weight=None,
        )

        updated_post = process_carousel_data({
            'request_type': '0x70',
            'post_number': 3,
            'full_weight': 40.5,
        })

        old_post.refresh_from_db()
        latest_post.refresh_from_db()
        self.assertEqual(updated_post.pk, latest_post.pk)
        self.assertTrue(old_post.is_empty)
        self.assertFalse(latest_post.is_empty)
        self.assertEqual(latest_post.full_weight, 40.5)

    def test_request_0x70_raises_when_post_does_not_exist(self):
        with self.assertRaises(CarouselPostNotFoundError):
            process_carousel_data({
                'request_type': '0x70',
                'post_number': 20,
                'full_weight': 40.5,
            })

    def test_missing_request_type_is_invalid(self):
        with self.assertRaises(ValidationError):
            process_carousel_data({'post_number': 1})

    def test_unknown_request_type_is_invalid(self):
        with self.assertRaises(UnsupportedCarouselRequestError):
            process_carousel_data({
                'request_type': 'unknown',
                'post_number': 1,
            })
