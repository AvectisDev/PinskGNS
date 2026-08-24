from datetime import timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.utils import timezone

from filling_station.models import BalloonsBatch
from railway_service.models import RailwayTank, RailwayTankHistory
from ttn.models import AutoTtn, BalloonTtn, RailwayTtn
from ttn.services import (
    close_ttn_in_miriada,
    collect_tanks_for_railway_ttn,
    get_railway_ttn_gas_totals,
    save_auto_ttn,
    save_balloon_ttn,
    save_railway_ttn,
)
from .helpers import TtnFixturesMixin


class RailwayTankTotalsTests(TtnFixturesMixin, TestCase):
    def test_sums_latest_history_without_doubling(self):
        RailwayTankHistory.objects.create(
            tank=self.tank,
            railway_ttn='RW-1',
            gas_weight=Decimal('10'),
            netto_weight_ttn=Decimal('20'),
            arrival_at=timezone.now() - timedelta(days=2),
        )
        RailwayTankHistory.objects.create(
            tank=self.tank,
            railway_ttn='RW-1',
            gas_weight=Decimal('5'),
            netto_weight_ttn=Decimal('8'),
            arrival_at=timezone.now(),
        )

        tanks, scale_total, ttn_total, scales_incomplete, ttn_incomplete = collect_tanks_for_railway_ttn('RW-1')
        self.assertEqual(tanks.count(), 1)
        self.assertEqual(scale_total, 5.0)
        self.assertEqual(ttn_total, 8.0)
        self.assertFalse(scales_incomplete)
        self.assertFalse(ttn_incomplete)

    def test_marks_scales_incomplete_when_gas_weight_missing(self):
        RailwayTankHistory.objects.create(
            tank=self.tank,
            railway_ttn='RW-3',
            gas_weight=Decimal('10'),
            netto_weight_ttn=Decimal('20'),
            arrival_at=timezone.now(),
        )
        tank2 = RailwayTank.objects.create(registration_number=6002)
        RailwayTankHistory.objects.create(
            tank=tank2,
            railway_ttn='RW-3',
            empty_weight=Decimal('22.96'),
            netto_weight_ttn=Decimal('8'),
            arrival_at=timezone.now(),
        )

        totals = get_railway_ttn_gas_totals('RW-3')

        self.assertEqual(totals['scales']['amount'], Decimal('10'))
        self.assertTrue(totals['scales']['incomplete'])
        self.assertEqual(totals['ttn']['amount'], Decimal('28'))
        self.assertFalse(totals['ttn']['incomplete'])

    def test_update_gas_amounts_uses_latest_history(self):
        RailwayTankHistory.objects.create(
            tank=self.tank,
            railway_ttn='RW-2',
            gas_weight=Decimal('10'),
            netto_weight_ttn=Decimal('20'),
            arrival_at=timezone.now() - timedelta(days=1),
        )
        RailwayTankHistory.objects.create(
            tank=self.tank,
            railway_ttn='RW-2',
            gas_weight=Decimal('3'),
            netto_weight_ttn=Decimal('4'),
            arrival_at=timezone.now(),
        )
        ttn = RailwayTtn.objects.create(number='R-2', railway_ttn='RW-2')
        ttn.update_gas_amounts()
        ttn.refresh_from_db()
        self.assertEqual(ttn.total_gas_amount_by_scales, 3.0)
        self.assertEqual(ttn.total_gas_amount_by_ttn, 4.0)


class SaveTtnEnqueueTests(TtnFixturesMixin, TestCase):
    @patch('ttn.tasks.generate_1c_file.delay')
    def test_save_auto_ttn_enqueues_once(self, mock_delay):
        batch = self.make_auto_batch(weight_gas_amount=Decimal('12.5'))
        ttn = AutoTtn(number='A-1', batch=batch)
        with self.captureOnCommitCallbacks(execute=True):
            save_auto_ttn(ttn)
        mock_delay.assert_called_once_with('A-1')
        ttn.refresh_from_db()
        self.assertEqual(ttn.source_gas_amount, 'Весы')
        self.assertEqual(float(ttn.total_gas_amount), 12.5)

    @patch('ttn.tasks.generate_1c_file.delay')
    def test_save_balloon_ttn_enqueues_once(self, mock_delay):
        batch = BalloonsBatch.objects.create(
            batch_type='l',
            truck=self.truck,
            ttn_id=100,
            user=self.user,
        )
        ttn = BalloonTtn(number='B-1', loading_batch=batch)
        with self.captureOnCommitCallbacks(execute=True):
            save_balloon_ttn(ttn)
        mock_delay.assert_called_once_with('B-1')

    @patch('ttn.tasks.generate_1c_file.delay')
    def test_empty_balloon_number_does_not_enqueue(self, mock_delay):
        ttn = BalloonTtn(number='')
        with self.captureOnCommitCallbacks(execute=True):
            save_balloon_ttn(ttn)
        mock_delay.assert_not_called()

    @patch('ttn.tasks.generate_1c_file.delay')
    def test_save_railway_ttn_enqueues_once_after_set(self, mock_delay):
        RailwayTankHistory.objects.create(
            tank=self.tank,
            railway_ttn='RW-9',
            gas_weight=Decimal('1'),
            netto_weight_ttn=Decimal('2'),
            arrival_at=timezone.now(),
        )
        ttn = RailwayTtn(number='R-9')
        with self.captureOnCommitCallbacks(execute=True):
            save_railway_ttn(ttn, 'RW-9')
        mock_delay.assert_called_once_with('R-9')
        self.assertEqual(ttn.railway_tank_list.count(), 1)
        self.assertEqual(ttn.total_gas_amount_by_scales, 1.0)


class CloseTtnInMiriadaTests(TestCase):
    @patch('ttn.services.time.sleep')
    @patch('ttn.services._log_batch_balloons_on_ttn_close')
    @patch('ttn.services.requests.Session')
    def test_count_mismatch_is_not_retried(self, mock_session_cls, _log_batch, mock_sleep):
        session = mock_session_cls.return_value
        response = MagicMock()
        response.status_code = 403
        response.reason = 'Forbidden'
        response.text = '{"title": "Error", "description": "Количество не соответствует указанному в ТТН"}'
        session.send.return_value = response

        success, error = close_ttn_in_miriada(47900)
        self.assertFalse(success)
        self.assertEqual(error, 'Количество не соответствует указанному в ТТН')
        self.assertEqual(session.send.call_count, 1)
        mock_sleep.assert_not_called()

    @patch('ttn.services.time.sleep')
    @patch('ttn.services._log_batch_balloons_on_ttn_close')
    @patch('ttn.services.requests.Session')
    def test_timeout_is_retried(self, mock_session_cls, _log_batch, mock_sleep):
        session = mock_session_cls.return_value
        session.send.side_effect = Exception('timed out')

        success, error = close_ttn_in_miriada(47900)
        self.assertFalse(success)
        self.assertEqual(session.send.call_count, 3)
        self.assertEqual(mock_sleep.call_count, 2)
