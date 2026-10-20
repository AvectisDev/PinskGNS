"""Web views: retry-close и валидация формы партии."""

from unittest.mock import patch

from django.test import Client, TestCase
from django.urls import reverse

from filling_station.forms import BalloonsBatchForm
from filling_station.models import BatchStatus
from filling_station.tests.factories import (
    make_balloon,
    make_batch,
    make_reader,
    make_truck,
    make_user,
)


class WebBatchRetryCloseTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.client = Client()
        self.client.force_login(self.user)
        self.truck = make_truck()
        make_reader(6, function='l')
        self.batch = make_batch(
            batch_type='l',
            truck=self.truck,
            reader_number=6,
            amount_of_ttn=1,
            user=self.user,
        )
        self.balloon = make_balloon(nfc_tag='webclose01e0')

    @patch('ttn.services.close_ttn_in_miriada')
    @patch('filling_station.services.batches.post_status_to_miriada')
    def test_retry_close_post_success(self, mock_send, mock_close):
        mock_close.return_value = (True, None)
        from filling_station.services.batches import add_balloon_to_batch_by_nfc
        add_balloon_to_batch_by_nfc(self.batch, self.balloon.nfc_tag)
        mock_send.reset_mock()
        url = reverse('filling_station:balloon_loading_batch_retry_close', args=[self.batch.id])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.batch.refresh_from_db()
        self.assertEqual(self.batch.status, BatchStatus.COMPLETED)

    def test_retry_close_rejected_for_completed(self):
        self.batch.status = BatchStatus.COMPLETED
        self.batch.save(update_fields=['status'])
        url = reverse('filling_station:balloon_loading_batch_retry_close', args=[self.batch.id])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.batch.refresh_from_db()
        self.assertEqual(self.batch.status, BatchStatus.COMPLETED)


class BalloonsBatchFormTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.truck = make_truck()

    def _form_data(self, **overrides):
        data = {
            'batch_type': 'l',
            'truck': self.truck.id,
            'reader_number': 6,
            'ttn_id': 1,
            'amount_of_ttn': 10,
            'amount_of_sensor': 0,
            'amount_of_5_liters': 0,
            'amount_of_12_liters': 0,
            'amount_of_27_liters': 0,
            'amount_of_50_liters': 0,
            'balloons_type': 'e',
            'status': BatchStatus.ACTIVE,
        }
        data.update(overrides)
        return data

    def test_form_requires_amount_of_ttn(self):
        data = self._form_data()
        data.pop('amount_of_ttn')
        form = BalloonsBatchForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('amount_of_ttn', form.errors)

    def test_form_valid_with_amount_of_ttn(self):
        form = BalloonsBatchForm(data=self._form_data())
        self.assertTrue(form.is_valid(), form.errors)
