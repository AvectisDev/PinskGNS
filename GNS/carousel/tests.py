from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, MagicMock, patch
import asyncio
import socket
import time

from filling_station.models import ReaderSettings

from .models import Carousel, CarouselSettings
from .listener import cache, config, processing, protocol, transport
from .services import (
    CarouselPostNotFoundError,
    UnsupportedCarouselRequestError,
    get_carousel_settings_data,
    process_carousel_data,
)
from .validation import is_value_in_range


class RangeValidationTests(SimpleTestCase):
    def test_value_inside_range(self):
        self.assertTrue(is_value_in_range(18.0, 17.0, 19.0))

    def test_value_outside_range(self):
        self.assertFalse(is_value_in_range(16.0, 17.0, 19.0))
        self.assertFalse(is_value_in_range(20.0, 17.0, 19.0))


class CheckBalloonSizeTests(SimpleTestCase):
    def test_disabled_classify_always_50(self):
        self.assertEqual(processing.check_balloon_size(10000, classify=False), 50)
        self.assertEqual(processing.check_balloon_size(20000, classify=False), 50)

    def test_classify_27_and_50(self):
        self.assertEqual(
            processing.check_balloon_size(16000, classify=True, size_27_max_g=16000),
            27,
        )
        self.assertEqual(
            processing.check_balloon_size(16001, classify=True, size_27_max_g=16000),
            50,
        )

    def test_invalid_weight_falls_back_to_50(self):
        self.assertEqual(
            processing.check_balloon_size(0, classify=True, size_27_max_g=16000),
            50,
        )
        self.assertEqual(
            processing.check_balloon_size(-1, classify=True, size_27_max_g=16000),
            50,
        )


class LoadCarouselConfigsTests(TestCase):
    def setUp(self):
        # data-migration может сидить number 1..N — очищаем для изолированных кейсов
        CarouselSettings.objects.all().delete()
        self.reader_8 = ReaderSettings.objects.create(
            number=8, ip='10.0.0.8', need_cache=True
        )
        self.reader_9 = ReaderSettings.objects.create(
            number=9, ip='10.0.0.9', need_cache=True
        )

    def test_loads_two_active_instances(self):
        CarouselSettings.objects.create(
            number=1,
            name='Карусель 1',
            tcp_host='192.168.1.50',
            tcp_port=4001,
            rfid_reader=self.reader_8,
            is_active=True,
            user=None,
        )
        CarouselSettings.objects.create(
            number=2,
            name='Карусель 2',
            tcp_host='192.168.1.51',
            tcp_port=4002,
            rfid_reader=self.reader_9,
            is_active=True,
            user=None,
        )

        configs = config.load_carousel_configs()

        self.assertEqual(len(configs), 2)
        self.assertEqual(configs[0].number, 1)
        self.assertEqual(configs[0].tcp_host, '192.168.1.50')
        self.assertEqual(configs[0].tcp_port, 4001)
        self.assertEqual(configs[0].rfid_reader, 8)
        self.assertEqual(configs[1].number, 2)
        self.assertEqual(configs[1].tcp_host, '192.168.1.51')
        self.assertEqual(configs[1].tcp_port, 4002)
        self.assertEqual(configs[1].rfid_reader, 9)

    def test_skips_inactive_and_incomplete(self):
        CarouselSettings.objects.create(
            number=1,
            tcp_host='10.0.0.1',
            tcp_port=4001,
            rfid_reader=self.reader_8,
            is_active=False,
            user=None,
        )
        CarouselSettings.objects.create(
            number=2,
            tcp_host='',
            tcp_port=4001,
            rfid_reader=self.reader_8,
            is_active=True,
            user=None,
        )
        CarouselSettings.objects.create(
            number=3,
            tcp_host='10.0.0.3',
            tcp_port=4001,
            rfid_reader=self.reader_9,
            is_active=True,
            user=None,
        )

        configs = config.load_carousel_configs()

        self.assertEqual(len(configs), 1)
        self.assertEqual(configs[0].number, 3)


class GetCarouselSettingsDataTests(TestCase):
    def setUp(self):
        from carousel.settings_cache import (
            REDIS_HASH_KEY,
            REDIS_REV_KEY,
            reset_cache_for_tests,
        )
        from core.redis_queue import get_redis_client

        reset_cache_for_tests()
        client = get_redis_client()
        client.delete(REDIS_HASH_KEY, REDIS_REV_KEY)
        CarouselSettings.objects.all().delete()

    def test_returns_settings_for_requested_number(self):
        CarouselSettings.objects.create(
            number=1,
            name='One',
            tcp_host='10.0.0.1',
            is_active=False,
            read_only=True,
            user=None,
        )
        CarouselSettings.objects.create(
            number=2,
            name='Two',
            tcp_host='10.0.0.2',
            is_active=False,
            read_only=False,
            user=None,
        )

        data = get_carousel_settings_data(2)

        self.assertIsNotNone(data)
        self.assertEqual(data['number'], 2)
        self.assertEqual(data['name'], 'Two')
        self.assertFalse(data['read_only'])

    def test_returns_none_when_missing(self):
        self.assertIsNone(get_carousel_settings_data(99))


class SettingsCacheSignalTests(TestCase):
    def setUp(self):
        from carousel.settings_cache import (
            REDIS_HASH_KEY,
            REDIS_REV_KEY,
            reset_cache_for_tests,
        )
        from core.redis_queue import get_redis_client

        reset_cache_for_tests()
        self.redis = get_redis_client()
        self.redis.delete(REDIS_HASH_KEY, REDIS_REV_KEY)
        CarouselSettings.objects.all().delete()

    def test_save_updates_cache_and_bumps_redis_rev(self):
        from carousel.settings_cache import REDIS_REV_KEY, get_settings_dict

        row = CarouselSettings.objects.create(
            number=1,
            name='Cached',
            weight_correction_value=1.5,
            use_weight_management=True,
            use_common_correction=True,
            is_active=False,
            user=None,
        )
        data = get_settings_dict(1)
        self.assertIsNotNone(data)
        self.assertEqual(data['weight_correction_value'], 1.5)
        rev_after_create = int(self.redis.get(REDIS_REV_KEY) or 0)
        self.assertGreater(rev_after_create, 0)

        row.weight_correction_value = 3.25
        row.save(update_fields=['weight_correction_value'])

        data = get_settings_dict(1)
        self.assertEqual(data['weight_correction_value'], 3.25)
        self.assertGreater(
            int(self.redis.get(REDIS_REV_KEY) or 0),
            rev_after_create,
        )

    def test_delete_removes_from_cache(self):
        from carousel.settings_cache import get_settings_dict

        row = CarouselSettings.objects.create(
            number=5,
            is_active=False,
            user=None,
        )
        self.assertIsNotNone(get_settings_dict(5))
        row.delete()
        self.assertIsNone(get_settings_dict(5))

    def test_sync_from_redis_restores_after_local_reset(self):
        from carousel.listener.processing import check_settings
        from carousel.settings_cache import (
            get_settings_dict,
            reset_cache_for_tests,
            sync_from_redis_if_stale,
        )

        CarouselSettings.objects.create(
            number=1,
            use_weight_management=True,
            use_common_correction=True,
            weight_correction_value=7.0,
            read_only=False,
            is_active=False,
            user=None,
        )
        self.assertEqual(get_settings_dict(1)['weight_correction_value'], 7.0)

        reset_cache_for_tests()
        sync_from_redis_if_stale()
        post_settings = check_settings(1, post_number=1)
        self.assertTrue(post_settings.available)
        self.assertEqual(post_settings.weight_correction, 7.0)
        self.assertFalse(post_settings.read_only)


class AsyncTcpFrameAssemblyTests(IsolatedAsyncioTestCase):
    async def test_read_exact_assembles_fragments(self):
        frame = bytes.fromhex('7A141036B0000D53')
        reader = asyncio.StreamReader()
        reader.feed_data(frame[:3])
        reader.feed_data(frame[3:5])
        reader.feed_data(frame[5:])

        result = await transport.read_exact(reader, 8)

        self.assertEqual(result, frame)

    async def test_read_exact_raises_when_connection_closed(self):
        reader = asyncio.StreamReader()
        reader.feed_data(b'\x7A\x14')
        reader.feed_eof()

        with self.assertRaises(ConnectionError):
            await transport.read_exact(reader, 8)

    async def test_async_transport_assembles_fragments_across_timeout(self):
        frame = bytes.fromhex('7A141036B0000D53')
        reader = AsyncMock()
        reader.read = AsyncMock(
            side_effect=[
                frame[:2],
                TimeoutError(),
                frame[2:],
            ]
        )
        writer = MagicMock()
        writer.close = MagicMock()
        writer.wait_closed = AsyncMock()

        tcp_transport = transport.AsyncTcpTransport(
            '127.0.0.1',
            4001,
            1.0,
            reader=reader,
            writer=writer,
        )

        self.assertEqual(await tcp_transport.read_frame(8), b'')
        self.assertEqual(await tcp_transport.read_frame(8), frame)

    async def test_async_transport_write_uses_drain(self):
        reader = AsyncMock()
        writer = MagicMock()
        writer.write = MagicMock()
        writer.drain = AsyncMock()
        writer.close = MagicMock()
        writer.wait_closed = AsyncMock()

        tcp_transport = transport.AsyncTcpTransport(
            '127.0.0.1',
            4001,
            1.0,
            reader=reader,
            writer=writer,
        )

        payload = bytes.fromhex('5A14FFA410FF7D88')
        await tcp_transport.write(payload)

        writer.write.assert_called_once_with(payload)
        writer.drain.assert_awaited_once()

    async def test_stale_partial_buffer_raises_and_clears_buffer(self):
        reader = AsyncMock()
        reader.read = AsyncMock(
            side_effect=[b'\xC2\x9B', TimeoutError(), TimeoutError()]
        )
        writer = MagicMock()
        writer.close = MagicMock()
        writer.wait_closed = AsyncMock()

        tcp_transport = transport.AsyncTcpTransport(
            '127.0.0.1',
            4001,
            1.0,
            reader=reader,
            writer=writer,
        )

        self.assertEqual(await tcp_transport.read_frame(8), b'')
        # Эмулируем, что неполный кадр «завис» дольше порога.
        tcp_transport._partial_buffer_since = time.monotonic() - 11.0
        with self.assertRaises(transport.PartialBufferStaleError):
            await tcp_transport.read_frame(8)
        self.assertEqual(tcp_transport._buffer, bytearray())

    async def test_read_timeout_without_data_keeps_connection(self):
        """Тишина постов: пустой таймаут → b'', без закрытия соединения."""
        reader = AsyncMock()
        reader.read = AsyncMock(side_effect=TimeoutError())
        writer = MagicMock()
        writer.close = MagicMock()
        writer.wait_closed = AsyncMock()

        tcp_transport = transport.AsyncTcpTransport(
            '127.0.0.1',
            4001,
            1.0,
            reader=reader,
            writer=writer,
        )
        self.assertEqual(await tcp_transport.read_frame(8), b'')
        writer.close.assert_not_called()

    def test_enable_tcp_keepalive_sets_options(self):
        writer = MagicMock()
        sock = MagicMock()
        writer.get_extra_info = MagicMock(return_value=sock)

        transport._enable_tcp_keepalive(writer)

        sock.setsockopt.assert_any_call(
            socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1
        )


class CarouselRequestProcessingTests(SimpleTestCase):
    def setUp(self):
        cache.recent_requests.clear()

    def test_duplicate_request_reuses_response_from_memory(self):
        found, response = cache.get_cached_request(
            1, '0x7a', 1, 18000
        )
        self.assertFalse(found)
        self.assertIsNone(response)

        cache.cache_request_result(
            1, '0x7a', 1, 18000, b'response'
        )
        found, response = cache.get_cached_request(
            1, '0x7a', 1, 18000
        )
        self.assertTrue(found)
        self.assertEqual(response, b'response')

    def test_cache_keys_are_isolated_per_carousel(self):
        cache.cache_request_result(1, '0x7a', 1, 18000, b'response-1')
        found, response = cache.get_cached_request(2, '0x7a', 1, 18000)
        self.assertFalse(found)
        self.assertIsNone(response)

        found, response = cache.get_cached_request(1, '0x7a', 1, 18000)
        self.assertTrue(found)
        self.assertEqual(response, b'response-1')

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
            processing.request_processing(
                1, 'reader_8_balloon_queue', '0x7a', 1, 18500
            )
        )

        self.assertFalse(response_required)
        self.assertEqual(full_weight, 0)
        self.assertEqual(data['nfc_tag'], 'test-tag')
        self.assertEqual(data['empty_weight'], 18.5)
        self.assertEqual(data['carousel_number'], 1)

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
            processing.request_processing(
                1, 'reader_8_balloon_queue', '0x7a', 1, 18500
            )
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
            processing.request_processing(
                1, 'reader_8_balloon_queue', '0x7a', 1, 18500
            )
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
            carousel_number=1,
            post_number=3,
            is_empty=True,
            full_weight=None,
        )
        latest_post = Carousel.objects.create(
            carousel_number=1,
            post_number=3,
            is_empty=True,
            full_weight=None,
        )

        updated_post = process_carousel_data({
            'request_type': '0x70',
            'carousel_number': 1,
            'post_number': 3,
            'full_weight': 40.5,
        })

        old_post.refresh_from_db()
        latest_post.refresh_from_db()
        self.assertEqual(updated_post.pk, latest_post.pk)
        self.assertTrue(old_post.is_empty)
        self.assertFalse(latest_post.is_empty)
        self.assertEqual(latest_post.full_weight, 40.5)

    def test_request_0x70_filters_by_carousel_number(self):
        post_carousel_1 = Carousel.objects.create(
            carousel_number=1,
            post_number=5,
            is_empty=True,
            full_weight=None,
        )
        post_carousel_2 = Carousel.objects.create(
            carousel_number=2,
            post_number=5,
            is_empty=True,
            full_weight=None,
        )

        updated_post = process_carousel_data({
            'request_type': '0x70',
            'carousel_number': 2,
            'post_number': 5,
            'full_weight': 41.0,
        })

        post_carousel_1.refresh_from_db()
        post_carousel_2.refresh_from_db()
        self.assertEqual(updated_post.pk, post_carousel_2.pk)
        self.assertTrue(post_carousel_1.is_empty)
        self.assertFalse(post_carousel_2.is_empty)
        self.assertEqual(post_carousel_2.full_weight, 41.0)

    def test_request_0x70_raises_when_post_does_not_exist(self):
        with self.assertRaises(CarouselPostNotFoundError):
            process_carousel_data({
                'request_type': '0x70',
                'carousel_number': 1,
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
