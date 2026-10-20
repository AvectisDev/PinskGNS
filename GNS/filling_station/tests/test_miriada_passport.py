"""Тесты get_balloon_data_from_miriada и update_balloon_passport."""

from unittest.mock import MagicMock, patch

import requests
from django.test import TestCase, override_settings

from filling_station.exceptions import MiriadaAPIError
from filling_station.services.miriada import get_balloon_data_from_miriada
from filling_station.services.rfid import update_balloon_passport
from filling_station.tests.factories import make_balloon


class GetBalloonDataFromMiriadaTests(TestCase):
    def test_empty_nfc_returns_none(self):
        self.assertIsNone(get_balloon_data_from_miriada(''))
        self.assertIsNone(get_balloon_data_from_miriada(None))

    @override_settings(MIRIADA_REQUEST_RETRIES=1, MIRIADA_RETRY_DELAY_SECONDS=0)
    @patch('filling_station.services.miriada.time.sleep')
    @patch('filling_station.services.miriada.requests.get')
    def test_timeout_raises_after_retries(self, mock_get, mock_sleep):
        mock_get.side_effect = requests.Timeout('timed out')
        with self.assertRaises(MiriadaAPIError) as ctx:
            get_balloon_data_from_miriada('aabbccdde0')
        self.assertIn('ошибкой', str(ctx.exception).lower())
        self.assertEqual(mock_get.call_count, 2)

    @patch('filling_station.services.miriada.requests.get')
    def test_success_returns_processed_fields(self, mock_get):
        response = MagicMock()
        response.raise_for_status = MagicMock()
        response.json.return_value = {
            'status': 'Ok',
            'List': {
                'number': 'SN-1',
                'netto': '12.5',
                'brutto': '40.0',
                'status': 1,
            },
        }
        mock_get.return_value = response
        data = get_balloon_data_from_miriada('aabbccdde0')
        self.assertEqual(data['number'], 'SN-1')
        self.assertEqual(data['netto'], 12.5)
        self.assertEqual(data['brutto'], 40.0)
        self.assertTrue(data['status'])


class UpdateBalloonPassportTests(TestCase):
    @patch('filling_station.services.rfid.get_balloon_data_from_miriada')
    def test_persists_miriada_fields(self, mock_get):
        balloon = make_balloon(nfc_tag='pass001e0', update_passport_required=True)
        mock_get.return_value = {
            'number': 'PASS-99',
            'netto': 18.0,
            'brutto': 42.0,
            'status': True,
        }
        update_balloon_passport(balloon)
        balloon.refresh_from_db()
        self.assertEqual(balloon.serial_number, 'PASS-99')
        self.assertEqual(balloon.netto, 18.0)
        self.assertEqual(balloon.brutto, 42.0)
        self.assertTrue(balloon.filling_status)
        self.assertFalse(balloon.update_passport_required)
