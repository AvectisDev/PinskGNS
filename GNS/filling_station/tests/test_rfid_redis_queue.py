"""Тест add_balloon_to_cache → Redis FIFO."""

from unittest.mock import patch

from django.test import TestCase

from filling_station.services.rfid import add_balloon_to_cache
from filling_station.tests.factories import make_balloon, make_reader


class AddBalloonToCacheTests(TestCase):
    @patch('filling_station.services.rfid.push_json_to_queue')
    def test_pushes_json_with_balloon_fields(self, mock_push):
        mock_push.return_value = 1
        reader = make_reader(8, function='p', need_cache=True)
        balloon = make_balloon(
            nfc_tag='redis001e0',
            serial_number='R-1',
            size=50,
            netto=18.0,
            brutto=40.0,
            filling_status=True,
        )
        add_balloon_to_cache(balloon, reader)
        mock_push.assert_called_once()
        key, payload = mock_push.call_args[0][:2]
        self.assertIn('8', key)
        self.assertEqual(payload['nfc_tag'], 'redis001e0')
        self.assertEqual(payload['serial_number'], 'R-1')
        self.assertEqual(payload['size'], 50)
