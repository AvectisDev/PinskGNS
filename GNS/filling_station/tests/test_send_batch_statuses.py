"""Тесты send_batch_balloon_statuses_to_miriada."""

from unittest.mock import patch

from django.test import TestCase, override_settings

from filling_station.exceptions import MiriadaAPIError
from filling_station.services.batches import (
    add_balloon_to_batch_by_nfc,
    send_batch_balloon_statuses_to_miriada,
)
from filling_station.tests.factories import (
    make_balloon,
    make_batch,
    make_reader,
    make_truck,
    make_user,
)


@override_settings(MIRIADA_BATCH_SEND_WORKERS=2)
class SendBatchBalloonStatusesTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.truck = make_truck()
        make_reader(6, function='l')
        self.batch = make_batch(
            batch_type='l',
            truck=self.truck,
            reader_number=6,
            amount_of_ttn=3,
            user=self.user,
        )
        self.ok = make_balloon(nfc_tag='sendok001e0')
        self.bad = make_balloon(nfc_tag='sendbad01e0')

    @patch('filling_station.services.batches.post_status_to_miriada')
    def test_empty_nfc_list_marks_sent(self, mock_post):
        ok, err = send_batch_balloon_statuses_to_miriada(self.batch, nfc_tags=[])
        self.assertTrue(ok)
        self.assertIsNone(err)
        mock_post.assert_not_called()
        self.batch.refresh_from_db()
        self.assertTrue(self.batch.miriada_balloons_sent)

    @patch('filling_station.services.batches.post_status_to_miriada')
    def test_partial_failures_merge_into_errors(self, mock_post):
        def _send(url, payload, send_type, session=None):
            if payload['nfctag'] == self.bad.nfc_tag:
                raise MiriadaAPIError('Автомобиль не найден')

        mock_post.side_effect = _send
        add_balloon_to_batch_by_nfc(self.batch, self.ok.nfc_tag)
        add_balloon_to_batch_by_nfc(self.batch, self.bad.nfc_tag)
        mock_post.reset_mock()
        mock_post.side_effect = _send

        ok, err = send_batch_balloon_statuses_to_miriada(self.batch)
        self.assertFalse(ok)
        self.assertIsNotNone(err)
        self.batch.refresh_from_db()
        self.ok.refresh_from_db()
        self.bad.refresh_from_db()
        self.assertEqual(self.bad.miriada_status_error, 'Автомобиль не найден')
        self.assertEqual(self.ok.miriada_status_error, '')
        self.assertIn(self.bad.nfc_tag, self.batch.miriada_status_errors)

    @patch('filling_station.services.batches.post_status_to_miriada')
    def test_success_clears_balloon_error(self, mock_post):
        mock_post.side_effect = MiriadaAPIError('-8')
        add_balloon_to_batch_by_nfc(self.batch, self.ok.nfc_tag)
        self.ok.refresh_from_db()
        self.assertEqual(self.ok.miriada_status_error, '-8')

        mock_post.reset_mock()
        mock_post.side_effect = None
        ok, err = send_batch_balloon_statuses_to_miriada(
            self.batch, nfc_tags=[self.ok.nfc_tag]
        )
        self.assertTrue(ok)
        self.assertIsNone(err)
        self.ok.refresh_from_db()
        self.assertEqual(self.ok.miriada_status_error, '')
