"""Тесты общего клиента Интеллекта (core.intellect)."""

from datetime import datetime
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings
from django.utils import timezone

from core.intellect import (
    AUTOGAS_CAMERAS,
    KPP_CAMERAS,
    RAILWAY_CAMERA,
    check_on_station,
    get_intellect_data,
    get_plate_image,
    get_registration_number_list,
    get_start_time,
    get_transport_type,
    separation_string_date,
)


class IntellectStartTimeTests(SimpleTestCase):
    def test_start_time_is_three_hours_behind_local(self):
        local_naive = timezone.localtime().replace(tzinfo=None, microsecond=0)
        parsed = datetime.strptime(get_start_time(0)[:19], '%Y-%m-%dT%H:%M:%S')
        delta = local_naive - parsed
        self.assertGreaterEqual(delta.total_seconds(), 3 * 3600 - 2)
        self.assertLessEqual(delta.total_seconds(), 3 * 3600 + 2)

    def test_start_time_ends_with_millis(self):
        self.assertTrue(get_start_time(5).endswith('.000'))


class IntellectSeparationDateTests(SimpleTestCase):
    def test_adds_three_hours(self):
        date_part, time_part = separation_string_date('15.05.2023 10:30:00')
        self.assertEqual(date_part, '2023-05-15')
        self.assertEqual(time_part, '13:30')

    def test_invalid_format_raises(self):
        with self.assertRaises(ValueError):
            separation_string_date('not-a-date')


class IntellectTransportTypeTests(SimpleTestCase):
    def test_railway_tank(self):
        self.assertEqual(get_transport_type('78244795'), 'railway_tank')

    def test_passenger_car_skipped(self):
        self.assertEqual(get_transport_type('1AB2345'), '')

    def test_truck(self):
        self.assertEqual(get_transport_type('AI00081'), 'truck')

    def test_trailer(self):
        self.assertEqual(get_transport_type('A3779B1'), 'trailer')

    def test_wrong_length(self):
        self.assertEqual(get_transport_type('AI0008'), '')


class IntellectCheckOnStationTests(SimpleTestCase):
    def test_camera_27(self):
        self.assertTrue(check_on_station({'camera': 'Камера 27', 'direction': '1'}))
        self.assertFalse(check_on_station({'camera': 'Камера 27', 'direction': '2'}))

    def test_camera_28(self):
        self.assertTrue(check_on_station({'camera': 'Камера 28', 'direction': '2'}))
        self.assertFalse(check_on_station({'camera': 'Камера 28', 'direction': '1'}))

    def test_camera_23(self):
        self.assertTrue(check_on_station({'camera': 'Камера 23', 'direction': '4'}))
        self.assertFalse(check_on_station({'camera': 'Камера 23', 'direction': '3'}))

    def test_unknown_camera(self):
        self.assertIsNone(check_on_station({'camera': 'Камера 99', 'direction': '1'}))


@override_settings(INTELLECT_SERVER_ADDRESS='http://intellect.test')
class IntellectRequestTests(SimpleTestCase):
    @patch('core.intellect.get_intellect_data', return_value=[])
    @patch('core.intellect.get_start_time', return_value='2023-05-15T07:00:00.000')
    def test_registration_request_body_railway(self, _start, mock_get):
        get_registration_number_list({'id': '1', 'delta_minutes': 10})
        mock_get.assert_called_once_with({
            'id': '1',
            'time_from': '2023-05-15T07:00:00.000',
            'validaty_from': '',
        })

    @patch('core.intellect.get_intellect_data', return_value=[])
    @patch('core.intellect.get_start_time', return_value='2023-05-15T07:00:00.000')
    def test_registration_request_body_with_validity(self, _start, mock_get):
        get_registration_number_list({'id': '4,5', 'delta_minutes': 5})
        mock_get.assert_called_once_with({
            'id': '4,5',
            'time_from': '2023-05-15T07:00:00.000',
            'validaty_from': '85',
        })

    @patch('core.intellect.requests.post')
    def test_get_intellect_data_ok(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'Status': 'OK',
            'Protocols': [{'number': 'AI00081'}],
        }
        mock_post.return_value = mock_response

        result = get_intellect_data({'id': '1'})
        self.assertEqual(result, [{'number': 'AI00081'}])
        mock_post.assert_called_once_with(
            'http://intellect.test/lprserver/GetProtocolNumbers',
            json={'id': '1'},
            timeout=2,
        )

    @patch('core.intellect.requests.post')
    def test_get_intellect_data_bad_status(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {'Status': 'ERROR'}
        mock_post.return_value = mock_response
        self.assertEqual(get_intellect_data({'id': '1'}), [])

    @patch('core.intellect.requests.post', side_effect=ConnectionError('down'))
    def test_get_intellect_data_network_error(self, _mock_post):
        self.assertEqual(get_intellect_data({'id': '1'}), [])


@override_settings(INTELLECT_SERVER_ADDRESS='http://intellect.test')
class IntellectPlateImageTests(SimpleTestCase):
    @patch('core.intellect.requests.get')
    def test_returns_jpeg_bytes(self, mock_get):
        mock_response = MagicMock()
        mock_response.headers = {'Content-Type': 'image/jpeg'}
        mock_response.content = b'jpeg-bytes'
        mock_get.return_value = mock_response

        self.assertEqual(get_plate_image('42'), b'jpeg-bytes')
        mock_get.assert_called_once_with(
            'http://intellect.test/lprserver/GetImage/Frames/42',
            timeout=2,
        )

    @patch('core.intellect.requests.get')
    def test_non_jpeg_returns_none(self, mock_get):
        mock_response = MagicMock()
        mock_response.headers = {'Content-Type': 'text/plain'}
        mock_response.content = b'nope'
        mock_get.return_value = mock_response
        self.assertIsNone(get_plate_image('42'))

    @patch('core.intellect.requests.get', side_effect=ConnectionError('down'))
    def test_network_error_returns_none(self, _mock_get):
        self.assertIsNone(get_plate_image('42'))


class IntellectCameraWindowsTests(SimpleTestCase):
    def test_railway_window_10_minutes(self):
        self.assertEqual(RAILWAY_CAMERA, {'id': '1', 'delta_minutes': 10})

    def test_autogas_window_180_minutes(self):
        self.assertEqual(AUTOGAS_CAMERAS, {'id': '2,3', 'delta_minutes': 180})

    def test_kpp_window_5_minutes(self):
        self.assertEqual(KPP_CAMERAS, {'id': '4,5', 'delta_minutes': 5})
