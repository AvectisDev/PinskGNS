from unittest.mock import patch

from django.test import SimpleTestCase


class RailwayTasksSmokeTests(SimpleTestCase):
    @patch('railway_service.tasks._process_event')
    def test_tank_event_delegates(self, process_event):
        from railway_service.tasks import process_railway_tank_event

        payload = {'camera_worked': True}
        process_railway_tank_event(payload)
        process_event.assert_called_once_with(payload)

    @patch('railway_service.tasks._batch_started')
    def test_batch_started_delegates(self, batch_started):
        from railway_service.tasks import process_railway_batch_started

        payload = {'active': True, 'batch_type': 1}
        process_railway_batch_started(payload)
        batch_started.assert_called_once_with(payload)

    @patch('railway_service.tasks._batch_ended')
    def test_batch_ended_delegates(self, batch_ended):
        from railway_service.tasks import process_railway_batch_ended

        payload = {'active': False}
        process_railway_batch_ended(payload)
        batch_ended.assert_called_once_with(payload)
