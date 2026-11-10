from unittest.mock import MagicMock, patch

from django.core.cache import cache
from django.test import SimpleTestCase, TestCase, override_settings

from railway_service.models import RailwayBatch
from railway_service.services.batch_events import (
    process_railway_batch_ended,
    process_railway_batch_started,
)
from railway_service.services.intellect_match import (
    PENDING_WEIGHINGS_KEY,
    SEEN_PROTOCOL_IDS_KEY,
    PendingWeighing,
    get_pending_weighings,
    mark_protocols_seen,
    match_protocols_to_weighings,
    protocol_id,
    set_pending_weighings,
    sort_protocols_oldest_first,
)
from railway_service.services.status_log import log_railway_tank_status
from railway_service.services.tank_events import batch_process, process_railway_tank_event
from railway_service.tests.helpers import RailwayFixturesMixin


@override_settings(CACHES={
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'railway-tank-status-tests',
    }
})
class RailwayTankStatusLogTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    @patch('railway_service.services.status_log.logger')
    def test_status_logged_only_when_changed(self, logger):
        idle = 'stable_weight=35.38, camera_worked=False, on_station=False'
        log_railway_tank_status(idle)
        log_railway_tank_status(idle)
        logger.info.assert_called_once_with(idle)

        active = 'stable_weight=35.38, camera_worked=True, on_station=True'
        log_railway_tank_status(active)
        self.assertEqual(logger.info.call_count, 2)
        logger.info.assert_called_with(active)


@override_settings(
    CACHES={
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'railway-tank-event-tests',
        }
    },
    INTELLECT_RAILWAY_WAIT_SECONDS=2,
    INTELLECT_RAILWAY_ATTEMPTS=3,
    OCRYP_URL='',
)
class RailwayTankEventTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    @patch('railway_service.services.tank_events.write_tag')
    @patch('railway_service.services.intellect_match.get_registration_number_list')
    def test_skips_when_opc_incomplete(self, get_list, write_tag):
        process_railway_tank_event({
            'stable_weight': None,
            'camera_worked': True,
            'on_station': True,
        })
        get_list.assert_not_called()
        write_tag.assert_not_called()

    @patch('railway_service.services.tank_events.batch_process')
    @patch('railway_service.services.tank_events.tank_process')
    @patch('railway_service.services.intellect_match.get_plate_image', return_value=b'img')
    @patch('railway_service.services.tank_events.write_tag')
    @patch('railway_service.services.intellect_match.time.sleep')
    @patch('railway_service.services.intellect_match.get_registration_number_list')
    def test_processes_camera_event(
        self,
        get_list,
        sleep,
        write_tag,
        get_image,
        tank_process,
        batch_process_mock,
    ):
        get_list.return_value = [{
            'number': '12345678',
            'plate_numbers.id': 'p1',
            'date': '10.11.2026 00:01:00',
        }]
        tank = MagicMock()
        tank_process.return_value = tank

        process_railway_tank_event({
            'stable_weight': 35.38,
            'camera_worked': True,
            'on_station': True,
        })

        write_tag.assert_called_once_with('railway.camera_worked', False)
        sleep.assert_called_once_with(2)
        tank_process.assert_called_once_with(12345678, b'img', True, 35.38)
        batch_process_mock.assert_called_once_with(tank)
        self.assertEqual(get_pending_weighings(), [])

    @patch('railway_service.services.tank_events.batch_process')
    @patch('railway_service.services.tank_events.tank_process')
    @patch('railway_service.services.tank_events.write_tag')
    @patch('railway_service.services.intellect_match.time.sleep')
    @patch('railway_service.services.intellect_match.get_registration_number_list')
    def test_empty_list_three_times_keeps_weighing_in_cache(
        self,
        get_list,
        sleep,
        write_tag,
        tank_process,
        batch_process_mock,
    ):
        get_list.return_value = []

        process_railway_tank_event({
            'stable_weight': 36.24,
            'camera_worked': True,
            'on_station': False,
        })

        self.assertEqual(get_list.call_count, 3)
        self.assertEqual(sleep.call_count, 3)
        write_tag.assert_called_once_with('railway.camera_worked', False)
        tank_process.assert_not_called()
        batch_process_mock.assert_not_called()
        pending = get_pending_weighings()
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0].stable_weight, 36.24)
        self.assertFalse(pending[0].on_station)

    @patch('railway_service.services.tank_events.batch_process')
    @patch('railway_service.services.tank_events.tank_process')
    @patch('railway_service.services.intellect_match.get_plate_image', return_value=b'img')
    @patch('railway_service.services.tank_events.write_tag')
    @patch('railway_service.services.intellect_match.time.sleep')
    @patch('railway_service.services.intellect_match.get_registration_number_list')
    def test_two_new_protocols_pair_cache_then_current(
        self,
        get_list,
        sleep,
        write_tag,
        get_image,
        tank_process,
        batch_process_mock,
    ):
        set_pending_weighings([
            PendingWeighing(
                stable_weight=76.36,
                on_station=True,
                captured_at='2026-11-08T02:02:10',
            )
        ])
        get_list.return_value = [
            {
                'number': '11111111',
                'plate_numbers.id': 'old',
                'date': '08.11.2026 02:02:12',
            },
            {
                'number': '22222222',
                'plate_numbers.id': 'new',
                'date': '08.11.2026 02:03:42',
            },
        ]
        tank_process.side_effect = [MagicMock(), MagicMock()]

        process_railway_tank_event({
            'stable_weight': 73.20,
            'camera_worked': True,
            'on_station': True,
        })

        self.assertEqual(tank_process.call_count, 2)
        # Сначала текущая (поздний протокол), затем отложенная из кэша
        self.assertEqual(
            tank_process.call_args_list[0].args,
            (22222222, b'img', True, 73.20),
        )
        self.assertEqual(
            tank_process.call_args_list[1].args,
            (11111111, b'img', True, 76.36),
        )
        self.assertEqual(get_pending_weighings(), [])
        write_tag.assert_called_once_with('railway.camera_worked', False)

    @patch('railway_service.services.tank_events.batch_process')
    @patch('railway_service.services.tank_events.tank_process')
    @patch('railway_service.services.tank_events.write_tag')
    @patch('railway_service.services.intellect_match.time.sleep')
    @patch('railway_service.services.intellect_match.get_registration_number_list')
    def test_already_seen_protocol_is_not_reused(
        self,
        get_list,
        sleep,
        write_tag,
        tank_process,
        batch_process_mock,
    ):
        mark_protocols_seen(['p-seen'])
        get_list.return_value = [{
            'number': '78252475',
            'plate_numbers.id': 'p-seen',
            'date': '10.11.2026 00:02:27',
        }]

        process_railway_tank_event({
            'stable_weight': 32.92,
            'camera_worked': True,
            'on_station': False,
        })

        tank_process.assert_not_called()
        batch_process_mock.assert_not_called()
        self.assertEqual(len(get_pending_weighings()), 1)
        write_tag.assert_called_once_with('railway.camera_worked', False)

    @patch('railway_service.services.tank_events.batch_process')
    @patch('railway_service.services.tank_events.tank_process')
    @patch('railway_service.services.intellect_match.get_plate_image', return_value=b'img')
    @patch('railway_service.services.tank_events.write_tag')
    @patch('railway_service.services.intellect_match.time.sleep')
    @patch('railway_service.services.intellect_match.get_registration_number_list')
    def test_new_protocol_on_second_attempt_skips_third(
        self,
        get_list,
        sleep,
        write_tag,
        get_image,
        tank_process,
        batch_process_mock,
    ):
        get_list.side_effect = [
            [],
            [{
                'number': '57462855',
                'plate_numbers.id': 'p2',
                'date': '08.11.2026 02:06:06',
            }],
        ]
        tank_process.return_value = MagicMock()

        process_railway_tank_event({
            'stable_weight': 76.42,
            'camera_worked': True,
            'on_station': True,
        })

        self.assertEqual(get_list.call_count, 2)
        self.assertEqual(sleep.call_count, 2)
        tank_process.assert_called_once()
        write_tag.assert_called_once_with('railway.camera_worked', False)

    @patch('railway_service.services.tank_events.batch_process')
    @patch('railway_service.services.tank_events.tank_process')
    @patch('railway_service.services.tank_events.log_number_comparison')
    @patch('railway_service.services.intellect_match.get_plate_image', return_value=b'img')
    @patch('railway_service.services.tank_events.write_tag')
    @patch('railway_service.services.intellect_match.time.sleep')
    @patch('railway_service.services.intellect_match.get_registration_number_list')
    @override_settings(OCRYP_URL='http://ocr.example')
    def test_camera_clears_bit_on_ocr_connection_error(
        self,
        get_list,
        sleep,
        write_tag,
        get_image,
        log_compare,
        tank_process,
        batch_process_mock,
    ):
        get_list.return_value = [{
            'number': '76615582',
            'plate_numbers.id': 'p-ocr',
            'date': '10.11.2026 00:01:00',
        }]
        tank = MagicMock()
        tank_process.return_value = tank
        log_compare.side_effect = ConnectionError('OCR down')

        process_railway_tank_event({
            'stable_weight': 37.7,
            'camera_worked': True,
            'on_station': True,
        })

        write_tag.assert_called_once_with('railway.camera_worked', False)
        tank_process.assert_called_once()
        batch_process_mock.assert_called_once_with(tank)


class IntellectMatchUnitTests(SimpleTestCase):
    def test_match_pairs_oldest_first_leaves_extra_weighing(self):
        protocols = [
            {'number': '1', 'plate_numbers.id': 'a'},
        ]
        weighings = [
            PendingWeighing(10, True, 't1'),
            PendingWeighing(20, False, 't2'),
        ]
        with patch(
            'railway_service.services.intellect_match.get_plate_image',
            return_value=None,
        ):
            matched, remaining = match_protocols_to_weighings(protocols, weighings)
        self.assertEqual(len(matched), 1)
        self.assertEqual(matched[0].registration_number, 1)
        self.assertEqual(matched[0].weighing.stable_weight, 10)
        self.assertEqual(len(remaining), 1)
        self.assertEqual(remaining[0].stable_weight, 20)

    def test_sorts_by_intellect_date_field(self):
        protocols = [
            {
                'number': '78244589',
                'plate_numbers.id': '{F81FC91B-81DC-F111-83A4-BE3AF2B6059F}',
                'date': '09.11.2026 21:04:09',
            },
            {
                'number': '78252509',
                'plate_numbers.id': '{31B243A8-80DC-F111-83A4-BE3AF2B6059F}',
                'date': '09.11.2026 21:00:57',
            },
        ]
        ordered = sort_protocols_oldest_first(protocols)
        self.assertEqual(ordered[0]['number'], '78252509')
        self.assertEqual(ordered[1]['number'], '78244589')
        self.assertEqual(
            protocol_id(ordered[0]),
            '{31B243A8-80DC-F111-83A4-BE3AF2B6059F}',
        )


@override_settings(CACHES={
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'railway-batch-event-tests',
    }
})
class RailwayBatchEventTests(RailwayFixturesMixin, TestCase):
    def setUp(self):
        super().setUp()
        cache.clear()

    def test_started_creates_batch_with_type(self):
        process_railway_batch_started({'active': True, 'batch_type': 1})
        batch = RailwayBatch.objects.get()
        self.assertTrue(batch.is_active)
        self.assertEqual(batch.batch_type, RailwayBatch.BatchType.LOADING)

    def test_started_does_not_duplicate_active(self):
        first = RailwayBatch.objects.create(is_active=True, batch_type=2)
        process_railway_batch_started({'active': True, 'batch_type': 1})
        self.assertEqual(RailwayBatch.objects.filter(is_active=True).count(), 1)
        first.refresh_from_db()
        self.assertEqual(first.batch_type, RailwayBatch.BatchType.UNLOADING)

    def test_started_updates_unknown_type(self):
        batch = RailwayBatch.objects.create(
            is_active=True,
            batch_type=RailwayBatch.BatchType.UNKNOWN,
        )
        process_railway_batch_started({'active': True, 'batch_type': 2})
        batch.refresh_from_db()
        self.assertEqual(batch.batch_type, RailwayBatch.BatchType.UNLOADING)

    def test_ended_closes_active_batch(self):
        batch = RailwayBatch.objects.create(is_active=True, batch_type=1)
        process_railway_batch_ended({'active': False})
        batch.refresh_from_db()
        self.assertFalse(batch.is_active)
        self.assertIsNotNone(batch.completed_at)

    def test_ended_without_active_is_noop(self):
        """Reconnect Oct 15/19: active=False без партии в БД."""
        process_railway_batch_ended({'active': False})
        self.assertEqual(RailwayBatch.objects.count(), 0)

    def test_batch_process_adds_to_active_only(self):
        tank = self.make_tank(registration_number=111111)
        batch_process(tank)
        self.assertEqual(RailwayBatch.objects.count(), 0)

        batch = RailwayBatch.objects.create(is_active=True, batch_type=1)
        batch_process(tank)
        self.assertIn(tank, batch.railway_tank_list.all())

    @patch('railway_service.services.tank_events.tank_process')
    @patch('railway_service.services.intellect_match.get_plate_image', return_value=b'img')
    @patch('railway_service.services.intellect_match.time.sleep')
    @patch('railway_service.services.intellect_match.get_registration_number_list')
    @override_settings(
        INTELLECT_RAILWAY_WAIT_SECONDS=0,
        INTELLECT_RAILWAY_ATTEMPTS=1,
        OCRYP_URL='',
    )
    def test_ended_flushes_pending_before_close(
        self,
        get_list,
        sleep,
        get_image,
        tank_process,
    ):
        batch = RailwayBatch.objects.create(is_active=True, batch_type=1)
        set_pending_weighings([
            PendingWeighing(
                stable_weight=76.36,
                on_station=True,
                captured_at='2026-11-08T02:02:10',
            )
        ])
        get_list.return_value = [{
            'number': '78244589',
            'plate_numbers.id': 'flush-1',
            'date': '08.11.2026 02:02:15',
        }]
        tank = self.make_tank(registration_number=78244589)
        tank_process.return_value = tank

        process_railway_batch_ended({'active': False})

        tank_process.assert_called_once_with(78244589, b'img', True, 76.36)
        batch.refresh_from_db()
        self.assertFalse(batch.is_active)
        self.assertIn(tank, batch.railway_tank_list.all())
        self.assertIsNone(cache.get(PENDING_WEIGHINGS_KEY))

    @patch('railway_service.services.intellect_match.time.sleep')
    @patch('railway_service.services.intellect_match.get_registration_number_list')
    @override_settings(
        INTELLECT_RAILWAY_WAIT_SECONDS=0,
        INTELLECT_RAILWAY_ATTEMPTS=1,
    )
    def test_ended_clears_unmatched_pending(self, get_list, sleep):
        RailwayBatch.objects.create(is_active=True, batch_type=1)
        set_pending_weighings([
            PendingWeighing(76.36, True, '2026-11-08T02:02:10'),
        ])
        get_list.return_value = []

        process_railway_batch_ended({'active': False})

        self.assertIsNone(cache.get(PENDING_WEIGHINGS_KEY))
        self.assertIsNone(cache.get(SEEN_PROTOCOL_IDS_KEY))
