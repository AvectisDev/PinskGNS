from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase, override_settings

from autogas.batch_events import (
    VEHICLE_LIST_SIZE,
    VehicleCombo,
    build_manual_vehicle_list,
    find_on_station_combo,
    find_transports,
    format_list_line,
    get_transport_numbers,
    parse_vehicle_list_line,
    process_autogas_batch_complete,
    process_autogas_batch_create,
    process_autogas_batch_stopped,
    process_autogas_operator_confirm,
)
from autogas.models import AutoGasBatch
from opcua.melsoft_words import (
    empty_melsoft_words,
    pack_melsoft_string,
    unpack_melsoft_string,
)
from transport.models import Trailer, Truck
from .helpers import AutoGasFixturesMixin


def _list_mode_writes(write_tag):
    return [
        c for c in write_tag.call_args_list
        if c.args and c.args[0] == 'autogas.vehicle_select.list_mode'
    ]


def _tag_calls(write_tag, tag_name):
    return [
        c for c in write_tag.call_args_list
        if c.args and c.args[0] == tag_name
    ]


def _assert_packed(words, expected_text: str) -> None:
    """write_tags_wait получает WORD[17], не ASCII-строку."""
    assert isinstance(words, list), words
    assert unpack_melsoft_string(words) == expected_text


@override_settings(CACHES={
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'autogas-batch-events-tests',
    }
})
class AutoGasBatchEventTests(AutoGasFixturesMixin, TestCase):
    @patch('autogas.batch_events.write_tags_wait', return_value=True)
    @patch('autogas.batch_events.write_tag')
    @patch('autogas.batch_events.get_transport_numbers')
    def test_empty_numbers_pushes_manual_list(
        self,
        get_numbers,
        write_tag,
        write_tags_wait,
    ):
        get_numbers.return_value = []
        process_autogas_batch_create({
            'batch_type_code': 1,
            'gas_type': 2,
            'request_batch_create': True,
            'response_batch_create': False,
        })
        self.assertEqual(AutoGasBatch.objects.count(), 0)
        self.assertEqual(_list_mode_writes(write_tag), [])
        words = write_tags_wait.call_args.args[0]
        _assert_packed(words['autogas.vehicle_select.vehicle_list_0'], '1    AI0008-1')
        write_tag.assert_any_call('autogas.vehicle_select.proposed_ready', False)
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
    def test_unknown_batch_type_stops_batch(self, write_tag):
        process_autogas_batch_create({
            'batch_type_code': 0,
            'gas_type': 2,
            'request_batch_create': True,
            'response_batch_create': False,
        })
        self.assertEqual(AutoGasBatch.objects.count(), 0)
        write_tag.assert_called_once_with('autogas.stop_batch', True)

    @patch('autogas.batch_events.write_tags_wait', return_value=True)
    @patch('autogas.batch_events.write_tag')
    @patch('autogas.batch_events.get_transport_numbers')
    def test_camera_hit_proposes_without_creating_batch(
        self,
        get_numbers,
        write_tag,
        write_tags_wait,
    ):
        get_numbers.return_value = [self.truck.registration_number]
        process_autogas_batch_create({
            'batch_type_code': 1,
            'gas_type': 3,
            'request_batch_create': True,
            'response_batch_create': False,
        })
        self.assertEqual(AutoGasBatch.objects.count(), 0)
        words = write_tags_wait.call_args.args[0]
        _assert_packed(words['autogas.vehicle_select.proposed_truck_number'], 'AI0008-1')
        write_tag.assert_any_call('autogas.vehicle_select.proposed_ready', True)
        self.assertEqual(_list_mode_writes(write_tag), [])

    @patch('autogas.batch_events.write_tags_wait', return_value=True)
    @patch('autogas.batch_events.write_tag')
    @patch('autogas.batch_events.get_transport_numbers')
    def test_camera_miss_falls_back_to_on_station(
        self,
        get_numbers,
        write_tag,
        write_tags_wait,
    ):
        get_numbers.return_value = ['XX 9999-9']
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
        words = write_tags_wait.call_args.args[0]
        _assert_packed(words['autogas.vehicle_select.proposed_truck_number'], 'AI0008-1')
        self.assertEqual(_list_mode_writes(write_tag), [])

    @patch('autogas.batch_events.write_tags_wait', return_value=True)
    @patch('autogas.batch_events.write_tag')
    @patch('autogas.batch_events.get_transport_numbers')
    def test_propose_tractor_with_trailer_writes_trailer_and_clears_list(
        self,
        get_numbers,
        write_tag,
        write_tags_wait,
    ):
        Trailer.objects.filter(pk=self.trailer.pk).update(truck=self.tractor)
        self.trailer.refresh_from_db()
        get_numbers.return_value = [
            self.tractor.registration_number,
            self.trailer.registration_number,
        ]
        process_autogas_batch_create({
            'batch_type_code': 1,
            'gas_type': 2,
            'request_batch_create': True,
            'response_batch_create': False,
        })
        words = write_tags_wait.call_args.args[0]
        _assert_packed(words['autogas.vehicle_select.proposed_truck_number'], 'AH0193-1')
        _assert_packed(words['autogas.vehicle_select.proposed_trailer_number'], 'A3779B-1')
        empty = empty_melsoft_words()
        for i in range(VEHICLE_LIST_SIZE):
            self.assertEqual(words[f'autogas.vehicle_select.vehicle_list_{i}'], empty)
        write_tag.assert_any_call('autogas.vehicle_select.proposed_ready', True)

    @patch('autogas.batch_events.write_tags_wait', return_value=False)
    @patch('autogas.batch_events.write_tag')
    @patch('autogas.batch_events.get_transport_numbers')
    def test_manual_list_write_failure_keeps_ready_false(
        self,
        get_numbers,
        write_tag,
        write_tags_wait,
    ):
        get_numbers.return_value = []
        process_autogas_batch_create({
            'batch_type_code': 1,
            'gas_type': 2,
            'request_batch_create': True,
            'response_batch_create': False,
        })
        write_tag.assert_any_call('autogas.vehicle_select.proposed_ready', False)
        self.assertEqual(_tag_calls(write_tag, 'autogas.response_batch_create'), [])
        ready_true = [
            c for c in write_tag.call_args_list
            if c.args == ('autogas.vehicle_select.proposed_ready', True)
        ]
        self.assertEqual(ready_true, [])

    @patch('autogas.batch_events.write_tags_wait', return_value=True)
    @patch('autogas.batch_events.write_tag')
    @patch('autogas.batch_events.get_transport_numbers')
    def test_on_station_fallback_proposes(self, get_numbers, write_tag, write_tags_wait):
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
        words = write_tags_wait.call_args.args[0]
        _assert_packed(words['autogas.vehicle_select.proposed_truck_number'], 'AI0008-1')
        self.assertEqual(_list_mode_writes(write_tag), [])

    @patch('autogas.batch_events.write_tags_wait', return_value=False)
    @patch('autogas.batch_events.write_tag')
    @patch('autogas.batch_events.get_transport_numbers')
    def test_propose_does_not_set_ready_if_string_writes_fail(
        self,
        get_numbers,
        write_tag,
        write_tags_wait,
    ):
        get_numbers.return_value = [self.truck.registration_number]
        process_autogas_batch_create({
            'batch_type_code': 1,
            'gas_type': 2,
            'request_batch_create': True,
            'response_batch_create': False,
        })
        write_tags_wait.assert_called_once()
        ready_true = [
            c for c in write_tag.call_args_list
            if c.args == ('autogas.vehicle_select.proposed_ready', True)
        ]
        self.assertEqual(ready_true, [])

    @patch('autogas.batch_events.write_tag')
    def test_confirm_empty_proposed_numbers_clears_confirm(self, write_tag):
        """Oct 19 09:54: Confirm без номеров на ПЛК."""
        process_autogas_operator_confirm({
            'batch_type_code': 1,
            'gas_type': 2,
            'request_batch_create': True,
            'response_batch_create': False,
            'list_mode': False,
            'proposed_ready': True,
            'proposed_truck_number': '',
            'proposed_trailer_number': '',
            'selected_vehicle_index': -1,
            'operator_confirm': True,
        })
        self.assertEqual(AutoGasBatch.objects.count(), 0)
        write_tag.assert_called_with('autogas.vehicle_select.operator_confirm', False)

    @patch('autogas.batch_events.write_tag')
    def test_confirm_without_request_clears_confirm(self, write_tag):
        process_autogas_operator_confirm({
            'batch_type_code': 1,
            'gas_type': 2,
            'request_batch_create': False,
            'response_batch_create': False,
            'list_mode': False,
            'proposed_truck_number': self.truck.registration_number,
            'operator_confirm': True,
        })
        self.assertEqual(AutoGasBatch.objects.count(), 0)
        write_tag.assert_called_with('autogas.vehicle_select.operator_confirm', False)
        self.assertEqual(_tag_calls(write_tag, 'autogas.stop_batch'), [])

    @patch('autogas.batch_events.write_tag')
    def test_confirm_unknown_batch_type_stops(self, write_tag):
        process_autogas_operator_confirm({
            'batch_type_code': 0,
            'gas_type': 2,
            'request_batch_create': True,
            'response_batch_create': False,
            'list_mode': False,
            'proposed_truck_number': self.truck.registration_number,
            'operator_confirm': True,
        })
        self.assertEqual(AutoGasBatch.objects.count(), 0)
        write_tag.assert_any_call('autogas.stop_batch', True)
        write_tag.assert_any_call('autogas.vehicle_select.operator_confirm', False)

    @patch('autogas.batch_events.write_tag')
    def test_confirm_unknown_gas_type_stops(self, write_tag):
        process_autogas_operator_confirm({
            'batch_type_code': 1,
            'gas_type': 1,
            'request_batch_create': True,
            'response_batch_create': False,
            'list_mode': False,
            'proposed_truck_number': self.truck.registration_number,
            'operator_confirm': True,
        })
        self.assertEqual(AutoGasBatch.objects.count(), 0)
        write_tag.assert_any_call('autogas.stop_batch', True)
        write_tag.assert_any_call('autogas.vehicle_select.operator_confirm', False)

    @patch('autogas.batch_events.write_tag')
    def test_confirm_list_mode_bad_index_clears_confirm(self, write_tag):
        for index in ('x', -1, 10):
            write_tag.reset_mock()
            process_autogas_operator_confirm({
                'batch_type_code': 1,
                'gas_type': 2,
                'request_batch_create': True,
                'response_batch_create': False,
                'list_mode': True,
                'selected_vehicle_index': index,
                'vehicle_list_0': format_list_line(0, VehicleCombo(truck=self.truck)),
                'operator_confirm': True,
            })
            self.assertEqual(AutoGasBatch.objects.count(), 0)
            write_tag.assert_called_with('autogas.vehicle_select.operator_confirm', False)
            self.assertEqual(_tag_calls(write_tag, 'autogas.stop_batch'), [])

    @patch('autogas.batch_events.write_tag')
    def test_confirm_list_mode_blank_line_clears_confirm(self, write_tag):
        process_autogas_operator_confirm({
            'batch_type_code': 1,
            'gas_type': 2,
            'request_batch_create': True,
            'response_batch_create': False,
            'list_mode': True,
            'selected_vehicle_index': 0,
            'vehicle_list_0': '',
            'operator_confirm': True,
        })
        self.assertEqual(AutoGasBatch.objects.count(), 0)
        write_tag.assert_called_with('autogas.vehicle_select.operator_confirm', False)
        self.assertEqual(_tag_calls(write_tag, 'autogas.stop_batch'), [])

    @patch('autogas.batch_events.write_tag')
    def test_confirm_unknown_plate_clears_confirm(self, write_tag):
        process_autogas_operator_confirm({
            'batch_type_code': 1,
            'gas_type': 2,
            'request_batch_create': True,
            'response_batch_create': False,
            'list_mode': False,
            'proposed_truck_number': 'XX9999-9',
            'proposed_trailer_number': '',
            'operator_confirm': True,
        })
        self.assertEqual(AutoGasBatch.objects.count(), 0)
        write_tag.assert_called_with('autogas.vehicle_select.operator_confirm', False)
        self.assertEqual(_tag_calls(write_tag, 'autogas.stop_batch'), [])

    @patch('autogas.batch_events.write_tag')
    def test_confirm_tractor_without_trailer_clears_confirm(self, write_tag):
        Trailer.objects.filter(pk=self.trailer.pk).update(truck=self.truck)
        self.trailer.refresh_from_db()
        process_autogas_operator_confirm({
            'batch_type_code': 1,
            'gas_type': 2,
            'request_batch_create': True,
            'response_batch_create': False,
            'list_mode': False,
            'proposed_truck_number': self.tractor.registration_number,
            'proposed_trailer_number': '',
            'operator_confirm': True,
        })
        self.assertEqual(AutoGasBatch.objects.count(), 0)
        write_tag.assert_called_with('autogas.vehicle_select.operator_confirm', False)
        self.assertEqual(_tag_calls(write_tag, 'autogas.stop_batch'), [])

    @patch('autogas.batch_events.create_active_batch', side_effect=RuntimeError('db down'))
    @patch('autogas.batch_events.write_tag')
    def test_confirm_generic_create_error_clears_confirm_without_stop(
        self,
        write_tag,
        _create,
    ):
        process_autogas_operator_confirm({
            'batch_type_code': 1,
            'gas_type': 2,
            'request_batch_create': True,
            'response_batch_create': False,
            'list_mode': False,
            'proposed_truck_number': self.truck.registration_number,
            'proposed_trailer_number': '',
            'operator_confirm': True,
        })
        self.assertEqual(AutoGasBatch.objects.count(), 0)
        write_tag.assert_called_with('autogas.vehicle_select.operator_confirm', False)
        self.assertEqual(_tag_calls(write_tag, 'autogas.stop_batch'), [])
        self.assertEqual(_tag_calls(write_tag, 'autogas.response_batch_create'), [])

    @patch('autogas.batch_events.get_truck_capacity', return_value=None)
    @patch('autogas.batch_events.logger')
    @patch('autogas.batch_events.write_tag')
    def test_ack_skips_capacity_when_none(self, write_tag, logger, _capacity):
        process_autogas_operator_confirm({
            'batch_type_code': 1,
            'gas_type': 2,
            'request_batch_create': True,
            'response_batch_create': False,
            'list_mode': False,
            'proposed_truck_number': self.truck.registration_number,
            'proposed_trailer_number': '',
            'operator_confirm': True,
        })
        self.assertEqual(AutoGasBatch.objects.filter(is_active=True).count(), 1)
        self.assertEqual(_tag_calls(write_tag, 'autogas.truck_capacity'), [])
        logger.warning.assert_called()
        write_tag.assert_any_call('autogas.response_batch_create', True)
        write_tag.assert_any_call('autogas.vehicle_select.selected_vehicle_index', -1)
        empty = empty_melsoft_words()
        write_tag.assert_any_call('autogas.vehicle_select.proposed_truck_number', empty)
        write_tag.assert_any_call('autogas.vehicle_select.proposed_trailer_number', empty)
        write_tag.assert_any_call('autogas.vehicle_select.vehicle_list_0', empty)

    @patch('autogas.batch_events.get_truck_capacity', return_value=0)
    @patch('autogas.batch_events.logger')
    @patch('autogas.batch_events.write_tag')
    def test_ack_skips_capacity_when_zero_without_warning(
        self,
        write_tag,
        logger,
        _capacity,
    ):
        process_autogas_operator_confirm({
            'batch_type_code': 1,
            'gas_type': 2,
            'request_batch_create': True,
            'response_batch_create': False,
            'list_mode': False,
            'proposed_truck_number': self.truck.registration_number,
            'proposed_trailer_number': '',
            'operator_confirm': True,
        })
        self.assertEqual(AutoGasBatch.objects.filter(is_active=True).count(), 1)
        self.assertEqual(_tag_calls(write_tag, 'autogas.truck_capacity'), [])
        logger.warning.assert_not_called()
        write_tag.assert_any_call('autogas.response_batch_create', True)

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
        self.assertEqual(_list_mode_writes(write_tag), [])

    @patch('autogas.batch_events.write_tag')
    def test_confirm_propose_from_word_buffer(self, write_tag):
        """Confirm с proposed_* как WORD[17] с ПЛК."""
        process_autogas_operator_confirm({
            'batch_type_code': 1,
            'gas_type': 2,
            'request_batch_create': True,
            'response_batch_create': False,
            'list_mode': False,
            'proposed_ready': True,
            'proposed_truck_number': pack_melsoft_string('AI0008-1'),
            'proposed_trailer_number': empty_melsoft_words(),
            'selected_vehicle_index': -1,
            'operator_confirm': True,
        })
        batch = AutoGasBatch.objects.get()
        self.assertEqual(batch.truck_id, self.truck.pk)
        write_tag.assert_any_call('autogas.response_batch_create', True)

    @patch('autogas.batch_events.write_tag')
    def test_confirm_list_mode_from_word_buffer(self, write_tag):
        line = format_list_line(0, VehicleCombo(truck=self.truck))
        process_autogas_operator_confirm({
            'batch_type_code': 1,
            'gas_type': 2,
            'request_batch_create': True,
            'response_batch_create': False,
            'list_mode': True,
            'selected_vehicle_index': 0,
            'vehicle_list_0': pack_melsoft_string(line),
            'operator_confirm': True,
        })
        batch = AutoGasBatch.objects.get()
        self.assertEqual(batch.truck_id, self.truck.pk)

    @patch('autogas.batch_events.write_tag')
    def test_confirm_list_mode_parses_vehicle_list_line(self, write_tag):
        Trailer.objects.filter(pk=self.trailer.pk).update(truck=self.tractor)
        self.trailer.refresh_from_db()
        line = format_list_line(
            2,
            VehicleCombo(truck=self.tractor, trailer=self.trailer),
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
            'selected_vehicle_index': 2,
            'vehicle_list_2': line,
            'operator_confirm': True,
        })
        batch = AutoGasBatch.objects.get()
        self.assertEqual(batch.truck_id, self.tractor.pk)
        self.assertEqual(batch.trailer_id, self.trailer.pk)
        write_tag.assert_any_call('autogas.response_batch_create', True)

    @patch('autogas.batch_events.write_tag')
    def test_confirm_list_mode_truck_only(self, write_tag):
        line = format_list_line(0, VehicleCombo(truck=self.truck))
        process_autogas_operator_confirm({
            'batch_type_code': 1,
            'gas_type': 2,
            'request_batch_create': True,
            'response_batch_create': False,
            'list_mode': True,
            'selected_vehicle_index': 0,
            'vehicle_list_0': line,
            'operator_confirm': True,
        })
        batch = AutoGasBatch.objects.get()
        self.assertEqual(batch.truck_id, self.truck.pk)
        self.assertIsNone(batch.trailer_id)

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

    @patch('autogas.batch_events.write_tags_wait', return_value=True)
    @patch('autogas.batch_events.write_tag')
    @patch('autogas.batch_events.get_transport_numbers')
    def test_inactive_truck_skipped_for_camera(
        self,
        get_numbers,
        write_tag,
        write_tags_wait,
    ):
        self.truck.is_active = False
        self.truck.save(update_fields=['is_active'])
        Trailer.objects.filter(pk=self.trailer.pk).update(truck=self.tractor)
        self.trailer.refresh_from_db()
        get_numbers.return_value = [self.truck.registration_number]
        process_autogas_batch_create({
            'batch_type_code': 1,
            'gas_type': 2,
            'request_batch_create': True,
            'response_batch_create': False,
        })
        self.assertEqual(AutoGasBatch.objects.count(), 0)
        self.assertEqual(_list_mode_writes(write_tag), [])
        words = write_tags_wait.call_args.args[0]
        _assert_packed(
            words['autogas.vehicle_select.vehicle_list_0'],
            '1    AH0193-1    A3779B-1',
        )
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
    def test_complete_without_active_still_acks(self, write_tag):
        process_autogas_batch_complete({
            'gas_amount': 1,
            'request_batch_complete': True,
            'response_batch_complete': False,
        })
        write_tag.assert_called_once_with('autogas.response_batch_complete', True)

    @patch('autogas.batch_events.complete_active_batch', side_effect=RuntimeError('fail'))
    @patch('autogas.batch_events.write_tag')
    def test_complete_generic_error_does_not_ack(self, write_tag, _complete):
        process_autogas_batch_complete({
            'gas_amount': 1,
            'request_batch_complete': True,
            'response_batch_complete': False,
        })
        write_tag.assert_not_called()

    def test_stop_closes_active_batch(self):
        batch = self.make_batch(is_active=True)
        process_autogas_batch_stopped({'stop_batch': True})
        batch.refresh_from_db()
        self.assertFalse(batch.is_active)
        self.assertIsNotNone(batch.completed_at)

    def test_stop_without_active_is_noop(self):
        process_autogas_batch_stopped({'stop_batch': True})
        self.assertEqual(AutoGasBatch.objects.filter(is_active=True).count(), 0)

    def test_stop_false_is_ignored(self):
        batch = self.make_batch(is_active=True)
        process_autogas_batch_stopped({'stop_batch': False})
        batch.refresh_from_db()
        self.assertTrue(batch.is_active)

    def test_find_transports_empty_list(self):
        self.assertEqual(find_transports([]), (None, None))

    def test_find_transports_tractor_without_gas_trailer(self):
        Trailer.objects.filter(pk=self.trailer.pk).update(truck=self.truck)
        self.assertEqual(
            find_transports([self.tractor.registration_number]),
            (None, None),
        )

    def test_find_transports_foreign_trailer_replaced_by_linked(self):
        Trailer.objects.filter(pk=self.trailer.pk).update(truck=self.tractor)
        self.trailer.refresh_from_db()
        foreign = Trailer.objects.create(
            truck=self.truck,
            registration_number='A 1111B-1',
            type=self.trailer_type,
            max_mass_of_transported_gas=10000,
            is_active=True,
        )
        truck, trailer = find_transports([
            self.tractor.registration_number,
            foreign.registration_number,
        ])
        self.assertEqual(truck, self.tractor)
        self.assertEqual(trailer, self.trailer)

    def test_find_transports_cistern_forces_trailer_none(self):
        truck, trailer = find_transports([
            self.truck.registration_number,
            self.trailer.registration_number,
        ])
        self.assertEqual(truck, self.truck)
        self.assertIsNone(trailer)

    def test_find_on_station_tractor_with_linked_trailer(self):
        Trailer.objects.filter(pk=self.trailer.pk).update(truck=self.tractor)
        self.trailer.refresh_from_db()
        self.tractor.is_on_station = True
        self.tractor.save(update_fields=['is_on_station'])
        combo = find_on_station_combo()
        self.assertIsNotNone(combo)
        self.assertEqual(combo.truck, self.tractor)
        self.assertEqual(combo.trailer, self.trailer)

    def test_find_on_station_trailer_only(self):
        Trailer.objects.filter(pk=self.trailer.pk).update(
            truck=self.tractor,
            is_on_station=True,
        )
        self.trailer.refresh_from_db()
        self.tractor.is_on_station = False
        self.tractor.save(update_fields=['is_on_station'])
        combo = find_on_station_combo()
        self.assertIsNotNone(combo)
        self.assertEqual(combo.truck, self.tractor)
        self.assertEqual(combo.trailer, self.trailer)

    def test_find_on_station_prefers_cistern(self):
        Trailer.objects.filter(pk=self.trailer.pk).update(truck=self.tractor)
        self.trailer.refresh_from_db()
        self.truck.is_on_station = True
        self.truck.save(update_fields=['is_on_station'])
        self.tractor.is_on_station = True
        self.tractor.save(update_fields=['is_on_station'])
        combo = find_on_station_combo()
        self.assertEqual(combo.truck, self.truck)
        self.assertIsNone(combo.trailer)

    def test_find_on_station_none(self):
        self.assertIsNone(find_on_station_combo())

    def test_build_manual_vehicle_list_order_and_cap(self):
        Trailer.objects.filter(pk=self.trailer.pk).update(truck=self.tractor)
        self.trailer.refresh_from_db()
        self.truck.is_on_station = True
        self.truck.save(update_fields=['is_on_station'])

        for i in range(12):
            Truck.objects.create(
                registration_number=f'AI {1000 + i:04d}-1',
                type=self.truck_type,
                car_brand='МАЗ',
                max_mass_of_transported_gas=1000,
                is_active=True,
            )

        combos = build_manual_vehicle_list()
        self.assertEqual(len(combos), VEHICLE_LIST_SIZE)
        self.assertEqual(combos[0].truck, self.truck)
        self.assertTrue(all(
            c.trailer is not None or c.truck.type.type == 'Цистерна'
            for c in combos
        ))
        self.assertFalse(any(
            c.truck.pk == self.tractor.pk and c.trailer is None
            for c in combos
        ))

    def test_build_manual_list_excludes_tractor_without_trailer(self):
        Trailer.objects.filter(pk=self.trailer.pk).update(truck=self.truck)
        combos = build_manual_vehicle_list()
        truck_ids = {c.truck.pk for c in combos}
        self.assertNotIn(self.tractor.pk, truck_ids)

    @patch('autogas.batch_events.get_registration_number_list', side_effect=RuntimeError('down'))
    def test_get_transport_numbers_exception_returns_empty(self, _intellect):
        self.assertEqual(get_transport_numbers(), [])

    @patch('autogas.batch_events.get_registration_number_list', return_value=[])
    def test_get_transport_numbers_empty_response(self, _intellect):
        self.assertEqual(get_transport_numbers(), [])

    @patch(
        'autogas.batch_events.canonicalize_registration_number',
        side_effect=lambda n: '' if n == 'BAD' else n,
    )
    @patch(
        'autogas.batch_events.get_registration_number_list',
        return_value=[{'number': 'BAD'}, {'number': 'AI 0008-1'}],
    )
    def test_get_transport_numbers_drops_blank_canonical(self, _intellect, _canon):
        self.assertEqual(get_transport_numbers(), ['AI 0008-1'])

    def test_parse_vehicle_list_line(self):
        self.assertEqual(
            parse_vehicle_list_line('1    AH1245-1    A5679B-2'),
            ('AH 1245-1', 'A 5679B-2'),
        )
        self.assertEqual(
            parse_vehicle_list_line('2    AI0008-1'),
            ('AI 0008-1', None),
        )
        self.assertEqual(parse_vehicle_list_line(''), (None, None))
        self.assertEqual(parse_vehicle_list_line(None), (None, None))
        self.assertEqual(parse_vehicle_list_line('1'), (None, None))

    def test_format_list_line(self):
        self.assertEqual(
            format_list_line(0, VehicleCombo(truck=self.truck)),
            '1    AI0008-1',
        )
        Trailer.objects.filter(pk=self.trailer.pk).update(truck=self.tractor)
        self.trailer.refresh_from_db()
        self.assertEqual(
            format_list_line(1, VehicleCombo(truck=self.tractor, trailer=self.trailer)),
            '2    AH0193-1    A3779B-1',
        )

    @patch('autogas.batch_events.format_trailer_hmi', return_value='VERYLONGTRAILER12345')
    @patch('autogas.batch_events.format_truck_hmi', return_value='VERYLONGTRUCK123456789')
    def test_format_list_line_truncates_to_32(self, _truck_hmi, _trailer_hmi):
        Trailer.objects.filter(pk=self.trailer.pk).update(truck=self.tractor)
        self.trailer.refresh_from_db()
        line = format_list_line(
            0,
            VehicleCombo(truck=self.tractor, trailer=self.trailer),
        )
        self.assertEqual(len(line), 32)
