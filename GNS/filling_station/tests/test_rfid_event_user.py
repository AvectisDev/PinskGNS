from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from filling_station.models import Balloon, ReaderSettings
from filling_station.services.rfid import get_rfid_event_user, processing_request_with_nfc


@override_settings(RFID_EVENT_USERNAME='reader')
class RfidEventUserTests(TestCase):
    def setUp(self):
        try:
            User.objects.get(pk=1)
        except User.DoesNotExist:
            User.objects.create_user(id=1, username='default_operator', password='x')
        self.reader = ReaderSettings.objects.create(
            number=1,
            ip='10.10.2.21',
            status='empty',
        )

    @patch('filling_station.services.rfid.update_balloon_passport')
    @patch('filling_station.services.rfid.add_balloon_to_reader_table')
    def test_scan_assigns_reader_user(self, _reader_table, _passport):
        reader_user = User.objects.create_user(id=2, username='reader', password='x')
        result = processing_request_with_nfc('aabbccdde0', 1)
        self.assertIsNotNone(result)
        balloon, _ = result
        balloon.refresh_from_db()
        self.assertEqual(balloon.user_id, reader_user.pk)

    @patch('filling_station.services.rfid.update_balloon_passport')
    @patch('filling_station.services.rfid.add_balloon_to_reader_table')
    def test_scan_without_reader_user_keeps_model_default(self, _reader_table, _passport):
        result = processing_request_with_nfc('11223344e0', 1)
        self.assertIsNotNone(result)
        balloon, _ = result
        balloon.refresh_from_db()
        self.assertEqual(balloon.user_id, 1)

    @patch('filling_station.services.rfid.update_balloon_passport')
    @patch('filling_station.services.rfid.add_balloon_to_reader_table')
    def test_rescan_without_reader_user_keeps_existing_user(self, _reader_table, _passport):
        other = User.objects.create_user(id=2, username='operator', password='x')
        Balloon.objects.create(nfc_tag='55667788e0', user=other, status='full')
        result = processing_request_with_nfc('55667788e0', 1)
        self.assertIsNotNone(result)
        balloon, _ = result
        balloon.refresh_from_db()
        self.assertEqual(balloon.user_id, other.pk)
        self.assertEqual(balloon.status, 'empty')

    def test_get_rfid_event_user_returns_none_when_missing(self):
        self.assertIsNone(get_rfid_event_user())
