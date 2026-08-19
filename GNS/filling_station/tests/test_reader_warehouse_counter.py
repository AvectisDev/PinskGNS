from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase

from filling_station.models import DailyReaderCounter, ReaderSettings, TotalReadersCounter
from filling_station.services import (
    processing_request_with_nfc,
    processing_request_without_nfc,
)


class ReaderWarehouseCounterTests(TestCase):
    def setUp(self):
        try:
            User.objects.get(pk=1)
        except User.DoesNotExist:
            User.objects.create_user(id=1, username='rfid_operator', password='x')
        self.counter, _ = TotalReadersCounter.objects.get_or_create(
            pk=1,
            defaults={'total_empty': 0, 'total_full': 0},
        )
        self.reader_1 = ReaderSettings.objects.create(number=1, ip='10.10.2.21', status='empty')
        self.reader_6 = ReaderSettings.objects.create(number=6, ip='10.10.2.26', status='empty')

    def test_sensor_on_reader_6_adds_empty(self):
        reader = processing_request_without_nfc(6)
        self.assertIsInstance(reader, ReaderSettings)
        self.assertEqual(reader.number, 6)
        self.counter.refresh_from_db()
        self.assertEqual(self.counter.total_empty, 1)
        daily = DailyReaderCounter.objects.get(number=self.reader_6)
        self.assertEqual(daily.amount_of_sensor, 1)
        self.assertEqual(daily.amount_of_rfid, 0)

    @patch('filling_station.services.rfid.update_balloon_passport')
    @patch('filling_station.services.rfid.add_balloon_to_reader_table')
    def test_rfid_on_reader_6_does_not_add_empty(self, _reader_table, _passport):
        processing_request_with_nfc('aabbccdde0', 6)
        self.counter.refresh_from_db()
        self.assertEqual(self.counter.total_empty, 0)
        daily = DailyReaderCounter.objects.get(number=self.reader_6)
        self.assertEqual(daily.amount_of_rfid, 1)
        self.assertEqual(daily.amount_of_sensor, 0)

    @patch('filling_station.services.rfid.update_balloon_passport')
    @patch('filling_station.services.rfid.add_balloon_to_reader_table')
    def test_reader_6_sensor_then_rfid_counts_empty_once(self, _reader_table, _passport):
        processing_request_without_nfc(6)
        processing_request_with_nfc('aabbccdde0', 6)
        self.counter.refresh_from_db()
        self.assertEqual(self.counter.total_empty, 1)

    @patch('filling_station.services.rfid.update_balloon_passport')
    @patch('filling_station.services.rfid.add_balloon_to_reader_table')
    def test_rfid_on_reader_1_adds_empty(self, _reader_table, _passport):
        processing_request_with_nfc('11223344e0', 1)
        self.counter.refresh_from_db()
        self.assertEqual(self.counter.total_empty, 1)
