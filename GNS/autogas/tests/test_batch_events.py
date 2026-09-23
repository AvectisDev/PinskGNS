from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase

from autogas.batch_events import (
    build_manual_vehicle_list,
    process_autogas_batch_complete,
    process_autogas_batch_create,
    process_autogas_operator_confirm,
)
from autogas.models import AutoGasBatch
from filling_station.models import Trailer
from .helpers import AutoGasFixturesMixin


class AutoGasBatchEventTests(AutoGasFixturesMixin, TestCase):
    @patch('autogas.batch_events.write_tag')
    @patch('autogas.batch_events.get_transport_numbers')
    def test_empty_numbers_pushes_manual_list(self, get_numbers, write_tag):
        get_numbers.return_value = []
        process_autogas_batch_create({
            'batch_type_code': 1,
            'gas_type': 2,
            'request_batch_create': True,
            'response_batch_create': False,
        })
        self.assertEqual(AutoGasBatch.objects.count(), 0)
        write_tag.assert_any_call('autogas.vehicle_select.list_mode', True)
        write_tag.assert_any_call(
            'autogas.vehicle_select.vehicle_list_0',
            self.truck.registration_number,
        )
        response_calls = [
            c for c in write_tag.call_args_list
            if c.args[0] == 'autogas.response_batch_create'
        ]
        self.assertEqual(response_calls, [])

    @patch('autogas.batch_events.write_tag')
    def test_unknown_gas_type_stops_batch(self, write_tag):
        process_autogas_batch_create({
            'batch_type_code': 1,
            'gas_type': 1,
            'request_batch_create': True,
            'response_batch_create': False,
        })
        self.assertEqual(AutoGasBatch.objects.count(), 0)
        write_tag.assert_called_once_with('autogas.stop_batch', True)

    @patch('autogas.batch_events.write_tag')
    @patch('autogas.batch_events.get_transport_numbers')
    def test_camera_hit_proposes_without_creating_batch(self, get_numbers, write_tag):
        get_numbers.return_value = [self.truck.registration_number]
        process_autogas_batch_create({
            'batch_type_code': 1,
            'gas_type': 3,
            'request_batch_create': True,
            'response_batch_create': False,
        })
        self.assertEqual(AutoGasBatch.objects.count(), 0)
        write_tag.assert_any_call(
            'autogas.vehicle_select.proposed_truck_number',
            self.truck.registration_number,
        )
        write_tag.assert_any_call('autogas.vehicle_select.proposed_ready', True)
        write_tag.assert_any_call('autogas.vehicle_select.list_mode', False)

    @patch('autogas.batch_events.write_tag')
    @patch('autogas.batch_events.get_transport_numbers')
    def test_on_station_fallback_proposes(self, get_numbers, write_tag):
        get_numbers.return_value = []
        self.truck.is_on_station = True
        self.truck.save(update_fields=['is_on_station'])
        process_autogas_batch_create({
            'batch_type_code': 1,
            'gas_type': 2,
            'request_batch_create': True,
            'response_batch_create': False,
        })
        self.assertEqual(AutoGasBatch.objects.count(), 0)
        write_tag.assert_any_call('autogas.vehicle_select.proposed_ready', True)
        write_tag.assert_any_call(
            'autogas.vehicle_select.proposed_truck_number',
            self.truck.registration_number,
        )

    @patch('autogas.batch_events.write_tag')
    def test_confirm_propose_creates_batch(self, write_tag):
        process_autogas_operator_confirm({
            'batch_type_code': 1,
            'gas_type': 3,
            'request_batch_create': True,
            'response_batch_create': False,
            'list_mode': False,
            'proposed_ready': True,
            'proposed_truck_number': self.truck.registration_number,
            'proposed_trailer_number': '',
            'selected_vehicle_index': -1,
            'operator_confirm': True,
        })
        batch = AutoGasBatch.objects.get()
        self.assertTrue(batch.is_active)
        self.assertEqual(batch.batch_type, 'l')
        self.assertEqual(batch.gas_type, 'ПБА')
        self.assertEqual(batch.truck_id, self.truck.pk)
        write_tag.assert_any_call('autogas.truck_capacity', Decimal('20000'))
        write_tag.assert_any_call('autogas.response_batch_create', True)
        write_tag.assert_any_call('autogas.vehicle_select.operator_confirm', False)

    @patch('autogas.batch_events.write_tag')
    def test_confirm_list_index_creates_batch(self, write_tag):
        Trailer.objects.filter(pk=self.trailer.pk).update(truck=self.tractor)
        self.trailer.refresh_from_db()
        combos = build_manual_vehicle_list()
        self.assertGreaterEqual(len(combos), 2)
        idx = next(
            i for i, c in enumerate(combos)
            if c.truck.pk == self.tractor.pk
        )
        process_autogas_operator_confirm({
            'batch_type_code': 2,
            'gas_type': 2,
            'request_batch_create': True,
            'response_batch_create': False,
            'list_mode': True,
            'proposed_ready': False,
            'proposed_truck_number': '',
            'proposed_trailer_number': '',
            'selected_vehicle_index': idx,
            'operator_confirm': True,
        })
        batch = AutoGasBatch.objects.get()
        self.assertEqual(batch.truck_id, self.tractor.pk)
        self.assertEqual(batch.trailer_id, self.trailer.pk)
        write_tag.assert_any_call('autogas.response_batch_create', True)

    @patch('autogas.batch_events.write_tag')
    def test_confirm_stops_when_active_exists(self, write_tag):
        self.make_batch(is_active=True)
        process_autogas_operator_confirm({
            'batch_type_code': 1,
            'gas_type': 2,
            'request_batch_create': True,
            'response_batch_create': False,
            'list_mode': False,
            'proposed_truck_number': self.truck.registration_number,
            'proposed_trailer_number': '',
            'selected_vehicle_index': -1,
            'operator_confirm': True,
        })
        self.assertEqual(AutoGasBatch.objects.filter(is_active=True).count(), 1)
        write_tag.assert_any_call('autogas.stop_batch', True)

    @patch('autogas.batch_events.write_tag')
    def test_confirm_ignored_when_already_acked(self, write_tag):
        process_autogas_operator_confirm({
            'batch_type_code': 1,
            'gas_type': 2,
            'request_batch_create': True,
            'response_batch_create': True,
            'list_mode': False,
            'proposed_truck_number': self.truck.registration_number,
            'operator_confirm': True,
        })
        self.assertEqual(AutoGasBatch.objects.count(), 0)
        write_tag.assert_called_with('autogas.vehicle_select.operator_confirm', False)

    @patch('autogas.batch_events.write_tag')
    @patch('autogas.batch_events.get_transport_numbers')
    def test_inactive_truck_skipped_for_camera(self, get_numbers, write_tag):
        self.truck.is_active = False
        self.truck.save(update_fields=['is_active'])
        get_numbers.return_value = [self.truck.registration_number]
        process_autogas_batch_create({
            'batch_type_code': 1,
            'gas_type': 2,
            'request_batch_create': True,
            'response_batch_create': False,
        })
        self.assertEqual(AutoGasBatch.objects.count(), 0)
        write_tag.assert_any_call('autogas.vehicle_select.list_mode', True)
        propose_ready = [
            c for c in write_tag.call_args_list
            if c.args == ('autogas.vehicle_select.proposed_ready', True)
        ]
        self.assertEqual(propose_ready, [])

    @patch('autogas.batch_events.write_tag')
    def test_complete_batch(self, write_tag):
        batch = self.make_batch(is_active=True)
        process_autogas_batch_complete({
            'gas_amount': Decimal('12'),
            'truck_empty_weight': Decimal('1'),
            'truck_full_weight': Decimal('2'),
            'weight_gas_amount': Decimal('1'),
            'request_batch_complete': True,
            'response_batch_complete': False,
        })
        batch.refresh_from_db()
        self.assertFalse(batch.is_active)
        self.assertEqual(batch.gas_amount, Decimal('12'))
        write_tag.assert_called_once_with('autogas.response_batch_complete', True)

    @patch('autogas.batch_events.write_tag')
    def test_complete_without_active_does_not_ack(self, write_tag):
        process_autogas_batch_complete({
            'gas_amount': 1,
            'request_batch_complete': True,
            'response_batch_complete': False,
        })
        write_tag.assert_not_called()
