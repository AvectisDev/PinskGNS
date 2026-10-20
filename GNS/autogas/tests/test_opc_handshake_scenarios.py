"""Сценарии из opcua/autogas логов 19.10 без реального OPC."""

from unittest.mock import patch

from django.test import TestCase

from autogas.batch_events import (
    process_autogas_batch_create,
    process_autogas_operator_confirm,
)
from autogas.models import AutoGasBatch
from .helpers import AutoGasFixturesMixin


class Oct19HandshakeScenarioTests(AutoGasFixturesMixin, TestCase):
    @patch('autogas.batch_events.write_tags_wait', return_value=False)
    @patch('autogas.batch_events.write_tag')
    @patch('autogas.batch_events.get_transport_numbers')
    def test_string_fail_then_confirm_empty_creates_no_batch(
        self,
        get_numbers,
        write_tag,
        write_tags_wait,
    ):
        """
        Oct 19 09:53–09:54: propose enqueue → STRING fail → ready не ставим;
        Confirm с пустыми номерами → партии нет.
        """
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

    @patch('autogas.batch_events.write_tags_wait', return_value=True)
    @patch('autogas.batch_events.write_tag')
    @patch('autogas.batch_events.get_transport_numbers')
    def test_string_ack_then_confirm_creates_batch(
        self,
        get_numbers,
        write_tag,
        write_tags_wait,
    ):
        """После фикса A1/A2: ACK строк → ready → Confirm создаёт партию."""
        get_numbers.return_value = [self.truck.registration_number]
        process_autogas_batch_create({
            'batch_type_code': 1,
            'gas_type': 2,
            'request_batch_create': True,
            'response_batch_create': False,
        })
        write_tag.assert_any_call('autogas.vehicle_select.proposed_ready', True)

        process_autogas_operator_confirm({
            'batch_type_code': 1,
            'gas_type': 2,
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
        self.assertEqual(batch.truck_id, self.truck.pk)
