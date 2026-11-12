from __future__ import annotations

from unittest import TestCase
from unittest.mock import patch

from opcua.autogas_process_log import (
    format_process_snapshot,
    log_process_event,
    should_log_opc_change,
)
from opcua.registry import TAGS


class AutogasProcessLogTests(TestCase):
    def test_registry_has_process_and_scale_tags(self):
        for name in (
            'autogas.process_step',
            'autogas.is_active',
            'autogas.start_batch',
            'autogas.gas_filling_in_progress',
            'autogas.fill_percentage',
            'autogas.vehicle_scale.current_weight',
            'autogas.vehicle_scale.previous_weight',
            'autogas.vehicle_scale.is_stable',
            'autogas.vehicle_scale.start_stabilization_timer',
        ):
            self.assertIn(name, TAGS)
            self.assertIn('PLC_SU2', TAGS[name].node_id)

    def test_weight_change_throttled_by_delta(self):
        self.assertFalse(
            should_log_opc_change(
                'autogas.vehicle_scale.current_weight',
                10000.0,
                10005.0,
            )
        )
        self.assertTrue(
            should_log_opc_change(
                'autogas.vehicle_scale.current_weight',
                10000.0,
                10020.0,
            )
        )
        self.assertTrue(
            should_log_opc_change('autogas.process_step', 1, 2)
        )

    def test_format_process_snapshot_includes_changed_tag(self):
        message = format_process_snapshot(
            {
                'autogas.process_step': 2,
                'autogas.is_active': True,
                'autogas.vehicle_scale.is_stable': True,
                'autogas.truck_empty_weight': 12240.0,
            },
            'autogas.process_step',
        )
        self.assertIn('Δautogas.process_step', message)
        self.assertIn('step=2', message)
        self.assertIn('active=True', message)
        self.assertIn('empty=12240.0', message)

    @patch('opcua.autogas_process_log.autogas_logger')
    @patch('opcua.autogas_process_log.opcua_logger')
    def test_log_process_event_writes_both_loggers(self, opcua_log, autogas_log):
        log_process_event(
            'autogas.process_step',
            {'autogas.process_step': 1},
        )
        opcua_log.info.assert_called_once()
        autogas_log.info.assert_called_once()
        self.assertIn('step=1', opcua_log.info.call_args.args[0])

    @patch('opcua.autogas_process_log.autogas_logger')
    @patch('opcua.autogas_process_log.opcua_logger')
    def test_log_process_event_skips_noisy_weight(self, opcua_log, autogas_log):
        log_process_event(
            'autogas.vehicle_scale.current_weight',
            {'autogas.vehicle_scale.current_weight': 1.0},
        )
        opcua_log.info.assert_not_called()
        autogas_log.info.assert_not_called()
