"""RFID → партия: processing_request_with_nfc и deferral статусов."""

from unittest.mock import patch

from django.test import TestCase

from filling_station.models import BatchStatus
from filling_station.services.batches import (
    pause_balloons_batch,
    should_defer_balloon_status_to_batch_close,
    should_send_balloon_status_immediately,
)
from filling_station.services.rfid import processing_request_with_nfc
from filling_station.tests.factories import (
    make_balloon,
    make_batch,
    make_reader,
    make_truck,
    make_user,
)


class ShouldDeferBalloonStatusTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.truck = make_truck()
        make_reader(6, function='l')
        self.batch = make_batch(
            batch_type='l',
            truck=self.truck,
            reader_number=6,
            user=self.user,
        )

    def test_defer_true_when_active_batch_on_reader_6(self):
        self.assertTrue(should_defer_balloon_status_to_batch_close(6))

    def test_defer_false_when_batch_paused(self):
        pause_balloons_batch(self.batch)
        self.assertFalse(should_defer_balloon_status_to_batch_close(6))

    def test_defer_false_for_non_batch_reader(self):
        self.assertFalse(should_defer_balloon_status_to_batch_close(1))

    def test_send_immediately_only_reader_8(self):
        self.assertTrue(should_send_balloon_status_immediately(8))
        self.assertFalse(should_send_balloon_status_immediately(6))
        self.assertFalse(should_send_balloon_status_immediately(3))


class ProcessingRequestWithNfcBatchTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.truck = make_truck()
        self.reader = make_reader(6, function='l')
        self.batch = make_batch(
            batch_type='l',
            truck=self.truck,
            reader_number=6,
            amount_of_ttn=10,
            user=self.user,
        )
        self.nfc = 'rfidint001e0'

    @patch('filling_station.services.rfid.add_balloon_to_reader_table')
    @patch('filling_station.services.rfid.update_balloon_passport')
    @patch('filling_station.services.batches.post_status_to_miriada')
    def test_adds_to_active_batch_and_sends_miriada(
        self, mock_post, mock_passport, mock_reader_table
    ):
        result = processing_request_with_nfc(self.nfc, 6)
        self.assertIsNotNone(result)
        balloon, reader = result
        self.assertEqual(balloon.nfc_tag, self.nfc)
        self.assertEqual(reader.number, 6)
        self.batch.refresh_from_db()
        self.assertTrue(self.batch.balloon_list.filter(nfc_tag=self.nfc).exists())
        mock_post.assert_called_once()
        _url, payload, send_type = mock_post.call_args[0][:3]
        self.assertEqual(send_type, 'registering_in_warehouse')
        self.assertEqual(payload['nfctag'], self.nfc)

    @patch('filling_station.services.rfid.add_balloon_to_reader_table')
    @patch('filling_station.services.rfid.update_balloon_passport')
    @patch('filling_station.services.batches.post_status_to_miriada')
    def test_no_active_batch_does_not_call_miriada_status(
        self, mock_post, mock_passport, mock_reader_table
    ):
        pause_balloons_batch(self.batch)
        result = processing_request_with_nfc('rfidint002e0', 6)
        self.assertIsNotNone(result)
        mock_post.assert_not_called()
        self.batch.refresh_from_db()
        self.assertFalse(self.batch.balloon_list.filter(nfc_tag='rfidint002e0').exists())
