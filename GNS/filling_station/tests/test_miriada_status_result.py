"""Тесты разбора Result и ретраев при отправке статусов баллонов в Мириаду."""

from unittest.mock import MagicMock, patch

import requests
from django.conf import settings
from django.test import TestCase, override_settings

from filling_station.exceptions import MiriadaAPIError
from filling_station.services.miriada import (
    _is_miriada_status_success,
    post_status_to_miriada,
)


class IsMiriadaStatusSuccessTests(TestCase):
    def test_result_ok_case_insensitive(self):
        self.assertTrue(_is_miriada_status_success({'Result': 'OK'}))
        self.assertTrue(_is_miriada_status_success({'result': 'ok'}))
        self.assertTrue(_is_miriada_status_success({'Result': 'Ok'}))

    def test_result_error_is_failure(self):
        self.assertFalse(_is_miriada_status_success({'Result': 'Error', 'message': -8}))
        self.assertFalse(_is_miriada_status_success({'result': 'error'}))
        self.assertFalse(_is_miriada_status_success({}))
        self.assertFalse(_is_miriada_status_success(None))


@override_settings(MIRIADA_REQUEST_RETRIES=2, MIRIADA_RETRY_DELAY_SECONDS=0)
class PostStatusToMiriadaResultTests(TestCase):
    def setUp(self):
        self.url = 'http://miriada.test/balloontocar'
        self.payload = {'nfctag': 'ad259727ae201de0', 'id_ttn': 1}
        self.send_type = 'registering_in_warehouse'

    def _mock_session(self, response=None, send_side_effect=None):
        session = MagicMock()
        prepared = MagicMock()
        prepared.url = self.url
        prepared.headers = {}
        prepared.body = b'{}'
        session.prepare_request.return_value = prepared
        if send_side_effect is not None:
            session.send.side_effect = send_side_effect
        else:
            session.send.return_value = response
        return session

    def test_http_200_result_error_raises_without_retry(self):
        response = MagicMock()
        response.status_code = 200
        response.reason = 'OK'
        response.text = '{"Result": "Error", "message": -8}'
        response.json.return_value = {'Result': 'Error', 'message': -8}
        session = self._mock_session(response)

        with self.assertRaises(MiriadaAPIError) as ctx:
            post_status_to_miriada(self.url, self.payload, self.send_type, session=session)

        self.assertEqual(str(ctx.exception), '-8')
        self.assertEqual(session.send.call_count, 1)

    def test_http_200_result_ok_succeeds(self):
        response = MagicMock()
        response.status_code = 200
        response.reason = 'OK'
        response.text = '{"Result": "OK"}'
        response.json.return_value = {'Result': 'OK'}
        session = self._mock_session(response)

        post_status_to_miriada(self.url, self.payload, self.send_type, session=session)
        self.assertEqual(session.send.call_count, 1)

    def test_http_200_result_lowercase_ok_succeeds(self):
        response = MagicMock()
        response.status_code = 200
        response.reason = 'OK'
        response.text = '{"result": "ok"}'
        response.json.return_value = {'result': 'ok'}
        session = self._mock_session(response)

        post_status_to_miriada(self.url, self.payload, self.send_type, session=session)
        self.assertEqual(session.send.call_count, 1)

    def test_http_403_is_not_retried(self):
        response = MagicMock()
        response.status_code = 403
        response.reason = 'Forbidden'
        response.text = 'Автомобиль не найден'
        session = self._mock_session(response)

        with self.assertRaises(MiriadaAPIError):
            post_status_to_miriada(self.url, self.payload, self.send_type, session=session)

        self.assertEqual(session.send.call_count, 1)

    @patch('filling_station.services.miriada.time.sleep')
    def test_timeout_is_retried(self, mock_sleep):
        session = self._mock_session(send_side_effect=requests.Timeout('timed out'))

        with self.assertRaises(MiriadaAPIError):
            post_status_to_miriada(self.url, self.payload, self.send_type, session=session)

        expected_attempts = settings.MIRIADA_REQUEST_RETRIES + 1
        self.assertEqual(session.send.call_count, expected_attempts)
        self.assertEqual(mock_sleep.call_count, settings.MIRIADA_REQUEST_RETRIES)
