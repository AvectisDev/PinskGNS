"""Тесты параллельного сравнения номера Интеллекта с ocryp."""

from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings

from railway_service.services import ocryp


@override_settings(OCRYP_URL='http://127.0.0.1:8001/recognize', OCRYP_TIMEOUT=5)
class RecognizeWagonNumberTests(SimpleTestCase):
    @patch('railway_service.services.ocryp.requests.post')
    def test_success_returns_number(self, mock_post):
        mock_post.return_value = _json_response(
            200,
            {
                'number': '78244795',
                'candidates': ['78244795'],
                'elapsed_seconds': 1.234,
            },
        )

        result = ocryp.recognize_wagon_number(b'jpeg-bytes')

        self.assertEqual(result.number, '78244795')
        self.assertEqual(result.candidates, ('78244795',))
        self.assertEqual(result.elapsed_seconds, 1.234)
        self.assertIsNone(result.error)
        mock_post.assert_called_once()
        _, kwargs = mock_post.call_args
        self.assertIn('files', kwargs)
        self.assertEqual(kwargs['timeout'], 5)

    @patch('railway_service.services.ocryp.requests.post')
    def test_null_number(self, mock_post):
        mock_post.return_value = _json_response(
            200,
            {'number': None, 'candidates': [], 'elapsed_seconds': 0.5},
        )

        result = ocryp.recognize_wagon_number(b'jpeg-bytes')

        self.assertIsNone(result.number)
        self.assertEqual(result.error, 'null_number')

    @patch('railway_service.services.ocryp.requests.post')
    def test_http_503(self, mock_post):
        mock_post.return_value = _json_response(503, {'detail': 'busy'})

        result = ocryp.recognize_wagon_number(b'jpeg-bytes')

        self.assertEqual(result.error, 'http_503')
        self.assertIsNone(result.number)

    @patch('railway_service.services.ocryp.requests.post')
    def test_timeout(self, mock_post):
        mock_post.side_effect = ocryp.requests.Timeout()

        result = ocryp.recognize_wagon_number(b'jpeg-bytes')

        self.assertEqual(result.error, 'timeout')

    @override_settings(OCRYP_URL='')
    def test_not_configured(self):
        result = ocryp.recognize_wagon_number(b'jpeg-bytes')

        self.assertEqual(result.error, 'not_configured')


@override_settings(OCRYP_URL='http://127.0.0.1:8001/recognize', OCRYP_TIMEOUT=5)
class LogNumberComparisonTests(SimpleTestCase):
    @patch('railway_service.services.ocryp.compare_logger')
    @patch('railway_service.services.ocryp.logger')
    @patch('railway_service.services.ocryp.recognize_wagon_number')
    def test_match_yes(self, mock_recognize, mock_railway_logger, mock_compare_logger):
        mock_recognize.return_value = ocryp.OcrypResult(
            number='78244795',
            candidates=('78244795',),
            elapsed_seconds=1.1,
        )

        ocryp.log_number_comparison(78244795, b'jpeg')

        message = mock_compare_logger.info.call_args[0][0]
        self.assertIn('intellect=78244795', message)
        self.assertIn('ocr=78244795', message)
        self.assertIn('match=yes', message)
        self.assertIn('candidates=78244795', message)
        self.assertIn('elapsed_s=1.1', message)
        mock_railway_logger.debug.assert_called_once()
        mock_railway_logger.info.assert_not_called()

    @patch('railway_service.services.ocryp.compare_logger')
    @patch('railway_service.services.ocryp.logger')
    @patch('railway_service.services.ocryp.recognize_wagon_number')
    def test_match_no_different_numbers(
        self, mock_recognize, mock_railway_logger, mock_compare_logger
    ):
        mock_recognize.return_value = ocryp.OcrypResult(
            number='78244800',
            candidates=('78244800',),
            elapsed_seconds=1.0,
        )

        ocryp.log_number_comparison(78244795, b'jpeg')

        message = mock_compare_logger.info.call_args[0][0]
        self.assertIn('match=no', message)
        self.assertIn('ocr=78244800', message)
        mock_railway_logger.info.assert_called_once()

    @patch('railway_service.services.ocryp.compare_logger')
    @patch('railway_service.services.ocryp.logger')
    @patch('railway_service.services.ocryp.recognize_wagon_number')
    def test_null_number_logged_as_mismatch(
        self, mock_recognize, mock_railway_logger, mock_compare_logger
    ):
        mock_recognize.return_value = ocryp.OcrypResult(error='null_number')

        ocryp.log_number_comparison(78244795, b'jpeg')

        message = mock_compare_logger.info.call_args[0][0]
        self.assertIn('match=no', message)
        self.assertIn('error=null_number', message)
        mock_railway_logger.info.assert_called_once()

    @patch('railway_service.services.ocryp.compare_logger')
    @patch('railway_service.services.ocryp.logger')
    @patch('railway_service.services.ocryp.recognize_wagon_number')
    def test_timeout_logged_as_mismatch(
        self, mock_recognize, mock_railway_logger, mock_compare_logger
    ):
        mock_recognize.return_value = ocryp.OcrypResult(error='timeout')

        ocryp.log_number_comparison(78244795, b'jpeg')

        message = mock_compare_logger.info.call_args[0][0]
        self.assertIn('match=no', message)
        self.assertIn('error=timeout', message)

    @patch('railway_service.services.ocryp.compare_logger')
    @patch('railway_service.services.ocryp.logger')
    @patch('railway_service.services.ocryp.recognize_wagon_number')
    def test_no_photo_skips_request(
        self, mock_recognize, mock_railway_logger, mock_compare_logger
    ):
        ocryp.log_number_comparison(78244795, None)

        mock_recognize.assert_not_called()
        message = mock_compare_logger.info.call_args[0][0]
        self.assertIn('match=no', message)
        self.assertIn('error=no_photo', message)
        mock_railway_logger.info.assert_called_once()


def _json_response(status_code: int, payload: dict) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = payload
    return response
