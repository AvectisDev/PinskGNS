from datetime import datetime

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone

from filling_station.models import Truck
from transport.management.commands.intellect import get_start_time
from transport.services import (
    close_all_on_station,
    find_vehicle,
    process_kpp_event,
    process_kpp_events,
)
from .helpers import TransportFixturesMixin

ENTRY_EVENT = {
    'number': 'AA1234-7',
    'camera': 'Камера 28',
    'direction': '2',
}

EXIT_EVENT = {
    'number': 'AA1234-7',
    'camera': 'Камера 27',
    'direction': '2',
}

UNKNOWN_DIRECTION_EVENT = {
    'number': 'AA1234-7',
    'camera': 'Камера 99',
    'direction': '1',
}


@override_settings(CACHES={
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'transport-kpp-tests',
    }
})
class KppServiceTests(TransportFixturesMixin, TestCase):
    def setUp(self):
        super().setUp()
        cache.clear()

    def test_unknown_direction_does_not_mark_departure(self):
        process_kpp_event(UNKNOWN_DIRECTION_EVENT)
        self.truck.refresh_from_db()
        self.assertFalse(self.truck.is_on_station)
        self.assertIsNone(self.truck.departure_at)

    def test_empty_number_does_not_break_loop(self):
        process_kpp_events([
            {'number': '', 'camera': 'Камера 28', 'direction': '2'},
            {'number': None, 'camera': 'Камера 28', 'direction': '2'},
            ENTRY_EVENT,
        ])
        self.truck.refresh_from_db()
        self.assertTrue(self.truck.is_on_station)

    def test_repeat_entry_does_not_shift_entry_at(self):
        process_kpp_event(ENTRY_EVENT)
        self.truck.refresh_from_db()
        first_entry = self.truck.entry_at
        self.assertIsNotNone(first_entry)

        cache.clear()
        process_kpp_event(ENTRY_EVENT)
        self.truck.refresh_from_db()
        self.assertEqual(self.truck.entry_at, first_entry)
        self.assertTrue(self.truck.is_on_station)

    def test_exit_after_entry_uses_direction_cache(self):
        process_kpp_event(ENTRY_EVENT)
        self.truck.refresh_from_db()
        entry_at = self.truck.entry_at

        process_kpp_event(EXIT_EVENT)
        self.truck.refresh_from_db()
        self.assertFalse(self.truck.is_on_station)
        self.assertEqual(self.truck.entry_at, entry_at)
        self.assertIsNotNone(self.truck.departure_at)

    def test_finds_vehicle_by_orm_not_plate_length(self):
        self.assertEqual(len(self.truck.registration_number), 8)
        self.assertEqual(find_vehicle('AA1234-7'), self.truck)
        process_kpp_event(ENTRY_EVENT)
        self.truck.refresh_from_db()
        self.assertTrue(self.truck.is_on_station)

    def test_unknown_number_is_not_created(self):
        process_kpp_event({
            'number': 'ZZ9999-9',
            'camera': 'Камера 28',
            'direction': '2',
        })
        self.assertFalse(
            Truck.objects.filter(registration_number='ZZ9999-9').exists()
        )

    def test_close_all_on_station_only_active(self):
        self.truck.is_on_station = True
        self.truck.entry_at = timezone.now()
        self.truck.save(update_fields=['is_on_station', 'entry_at'])
        trucks, trailers = close_all_on_station()
        self.truck.refresh_from_db()
        self.trailer.refresh_from_db()
        self.assertEqual(trucks, 1)
        self.assertEqual(trailers, 0)
        self.assertFalse(self.truck.is_on_station)
        self.assertIsNotNone(self.truck.departure_at)
        self.assertFalse(self.trailer.is_on_station)

    def test_trailer_entry(self):
        process_kpp_event({
            'number': self.trailer.registration_number,
            'camera': 'Камера 28',
            'direction': '2',
        })
        self.trailer.refresh_from_db()
        self.assertTrue(self.trailer.is_on_station)


class IntellectTimeOffsetTests(TestCase):
    def test_start_time_is_three_hours_behind_local(self):
        local_naive = timezone.localtime().replace(tzinfo=None, microsecond=0)
        parsed = datetime.strptime(get_start_time(0)[:19], '%Y-%m-%dT%H:%M:%S')
        delta = local_naive - parsed
        self.assertGreaterEqual(delta.total_seconds(), 3 * 3600 - 2)
        self.assertLessEqual(delta.total_seconds(), 3 * 3600 + 2)
