from unittest.mock import patch

from django.test import SimpleTestCase


class AutogasTasksSmokeTests(SimpleTestCase):
    @patch('autogas.tasks._create')
    def test_process_autogas_batch_create_delegates(self, create):
        from autogas.tasks import process_autogas_batch_create

        payload = {'request_batch_create': True}
        process_autogas_batch_create(payload)
        create.assert_called_once_with(payload)

    @patch('autogas.tasks._confirm')
    def test_process_autogas_operator_confirm_delegates(self, confirm):
        from autogas.tasks import process_autogas_operator_confirm

        payload = {'operator_confirm': True}
        process_autogas_operator_confirm(payload)
        confirm.assert_called_once_with(payload)

    @patch('autogas.tasks._complete')
    def test_process_autogas_batch_complete_delegates(self, complete):
        from autogas.tasks import process_autogas_batch_complete

        payload = {'request_batch_complete': True}
        process_autogas_batch_complete(payload)
        complete.assert_called_once_with(payload)

    @patch('autogas.tasks._stopped')
    def test_process_autogas_batch_stopped_delegates(self, stopped):
        from autogas.tasks import process_autogas_batch_stopped

        payload = {'stop_batch': True}
        process_autogas_batch_stopped(payload)
        stopped.assert_called_once_with(payload)
