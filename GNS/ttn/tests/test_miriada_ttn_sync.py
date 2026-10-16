from datetime import date
from unittest.mock import MagicMock, patch

from django.test import TestCase

from ttn.models import MiriadaTtn, MiriadaTtnStatus
from ttn.services import close_ttn_in_miriada, sync_current_ttn_from_miriada


class SyncCurrentTtnFromMiriadaTests(TestCase):
    @patch('ttn.services.get_current_ttn_from_miriada')
    def test_sync_saves_operation_name(self, mock_get):
        mock_get.return_value = [
            {
                'ttn_id': 56615,
                'name': '0567005',
                'auto': 'AH 8918-1',
                'operation_name': 'Отпуск в ПУ/РГС',
                'date': date(2026, 10, 16),
            },
        ]
        saved = sync_current_ttn_from_miriada()
        self.assertEqual(saved, 1)
        ttn = MiriadaTtn.objects.get(ttn_id=56615)
        self.assertEqual(ttn.operation_name, 'Отпуск в ПУ/РГС')
        self.assertEqual(ttn.status, MiriadaTtnStatus.NOT_PROCESSED)

    @patch('ttn.services.get_current_ttn_from_miriada')
    def test_sync_does_not_reset_status(self, mock_get):
        MiriadaTtn.objects.create(
            ttn_id=56615,
            name='0567005',
            auto='AH 8918-1',
            operation_name='Старое',
            date=date(2026, 10, 15),
            status=MiriadaTtnStatus.CLOSED,
        )
        mock_get.return_value = [
            {
                'ttn_id': 56615,
                'name': '0567005',
                'auto': 'AH 8918-1',
                'operation_name': 'Отпуск в ПУ/РГС',
                'date': date(2026, 10, 16),
            },
        ]
        sync_current_ttn_from_miriada()
        ttn = MiriadaTtn.objects.get(ttn_id=56615)
        self.assertEqual(ttn.operation_name, 'Отпуск в ПУ/РГС')
        self.assertEqual(ttn.status, MiriadaTtnStatus.CLOSED)


class CloseTtnSetsMiriadaStatusTests(TestCase):
    def setUp(self):
        self.ttn = MiriadaTtn.objects.create(
            ttn_id=47900,
            name='T-1',
            auto='AM 0001-1',
            date=date(2026, 10, 16),
        )

    @patch('ttn.services._log_batch_balloons_on_ttn_close')
    @patch('ttn.services.requests.Session')
    def test_success_sets_closed(self, mock_session_cls, _log_batch):
        session = mock_session_cls.return_value
        response = MagicMock()
        response.status_code = 200
        response.reason = 'OK'
        response.text = '{"Result": "Ok"}'
        response.json.return_value = {'Result': 'Ok'}
        session.send.return_value = response

        success, error = close_ttn_in_miriada(47900)
        self.assertTrue(success)
        self.assertIsNone(error)
        self.ttn.refresh_from_db()
        self.assertEqual(self.ttn.status, MiriadaTtnStatus.CLOSED)

    @patch('ttn.services._log_batch_balloons_on_ttn_close')
    @patch('ttn.services.requests.Session')
    def test_error_sets_error_status(self, mock_session_cls, _log_batch):
        session = mock_session_cls.return_value
        response = MagicMock()
        response.status_code = 200
        response.reason = 'OK'
        response.text = '{"Result": "Error", "message": "fail"}'
        response.json.return_value = {'Result': 'Error', 'message': 'fail'}
        session.send.return_value = response

        success, error = close_ttn_in_miriada(47900)
        self.assertFalse(success)
        self.assertEqual(error, 'fail')
        self.ttn.refresh_from_db()
        self.assertEqual(self.ttn.status, MiriadaTtnStatus.ERROR)

    @patch('ttn.services._log_batch_balloons_on_ttn_close')
    @patch('ttn.services.requests.Session')
    def test_missing_local_ttn_does_not_create(self, mock_session_cls, _log_batch):
        session = mock_session_cls.return_value
        response = MagicMock()
        response.status_code = 200
        response.reason = 'OK'
        response.text = '{"Result": "Ok"}'
        response.json.return_value = {'Result': 'Ok'}
        session.send.return_value = response

        success, _ = close_ttn_in_miriada(99999)
        self.assertTrue(success)
        self.assertFalse(MiriadaTtn.objects.filter(ttn_id=99999).exists())
