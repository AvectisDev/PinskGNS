"""Диагностическое логирование процесса партии автоцистерн по OPC-снимку."""

from __future__ import annotations

import logging
from typing import Any, Mapping, Optional

opcua_logger = logging.getLogger('opcua')
autogas_logger = logging.getLogger('autogas')

# Смена этих тегов даёт компактную строку процесса (step/active/stable/...).
PROCESS_EVENT_TAGS: frozenset[str] = frozenset({
    'autogas.process_step',
    'autogas.is_active',
    'autogas.start_batch',
    'autogas.stop_batch',
    'autogas.gas_filling_in_progress',
    'autogas.request_batch_create',
    'autogas.response_batch_create',
    'autogas.request_batch_complete',
    'autogas.response_batch_complete',
    'autogas.batch_type_code',
    'autogas.gas_type',
    'autogas.truck_empty_weight',
    'autogas.truck_full_weight',
    'autogas.weight_gas_amount',
    'autogas.gas_amount',
    'autogas.truck_capacity',
    'autogas.fill_percentage',
    'autogas.initial_mass_meter',
    'autogas.final_mass_meter',
    'autogas.vehicle_scale.is_stable',
    'autogas.vehicle_scale.start_stabilization_timer',
    'autogas.vehicle_select.operator_confirm',
    'autogas.vehicle_select.proposed_ready',
    'autogas.vehicle_select.list_mode',
})

# Вес с платформы часто дёргается — в opcua.log пишем только заметные скачки.
WEIGHT_CHANGE_TAGS: frozenset[str] = frozenset({
    'autogas.vehicle_scale.current_weight',
    'autogas.vehicle_scale.previous_weight',
})
WEIGHT_LOG_DELTA = 10.0


def _num(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def should_log_opc_change(name: str, previous: Any, value: Any) -> bool:
    """Фильтр шумных тегов для строки OPC change."""
    if name not in WEIGHT_CHANGE_TAGS:
        return True
    prev_n = _num(previous)
    next_n = _num(value)
    if prev_n is None or next_n is None:
        return previous != value
    return abs(next_n - prev_n) >= WEIGHT_LOG_DELTA


def format_process_snapshot(snapshot: Mapping[str, Any], changed: str) -> str:
    """Одна строка: что изменилось + ключевое состояние партии/весов."""
    return (
        f'Autogas process Δ{changed}: '
        f'step={snapshot.get("autogas.process_step")}, '
        f'active={snapshot.get("autogas.is_active")}, '
        f'start={snapshot.get("autogas.start_batch")}, '
        f'stop={snapshot.get("autogas.stop_batch")}, '
        f'filling={snapshot.get("autogas.gas_filling_in_progress")}, '
        f'type={snapshot.get("autogas.batch_type_code")}, '
        f'gas={snapshot.get("autogas.gas_type")}, '
        f'req_create={snapshot.get("autogas.request_batch_create")}, '
        f'resp_create={snapshot.get("autogas.response_batch_create")}, '
        f'req_complete={snapshot.get("autogas.request_batch_complete")}, '
        f'resp_complete={snapshot.get("autogas.response_batch_complete")}, '
        f'empty={snapshot.get("autogas.truck_empty_weight")}, '
        f'full={snapshot.get("autogas.truck_full_weight")}, '
        f'w_gas={snapshot.get("autogas.weight_gas_amount")}, '
        f'm_gas={snapshot.get("autogas.gas_amount")}, '
        f'capacity={snapshot.get("autogas.truck_capacity")}, '
        f'fill%={snapshot.get("autogas.fill_percentage")}, '
        f'scale={snapshot.get("autogas.vehicle_scale.current_weight")}, '
        f'prev={snapshot.get("autogas.vehicle_scale.previous_weight")}, '
        f'stable={snapshot.get("autogas.vehicle_scale.is_stable")}, '
        f'stab_timer={snapshot.get("autogas.vehicle_scale.start_stabilization_timer")}, '
        f'confirm={snapshot.get("autogas.vehicle_select.operator_confirm")}, '
        f'proposed_ready={snapshot.get("autogas.vehicle_select.proposed_ready")}, '
        f'list_mode={snapshot.get("autogas.vehicle_select.list_mode")}'
    )


def log_process_event(changed: str, snapshot: Mapping[str, Any]) -> None:
    """Пишет снимок процесса в opcua.log и autogas.log."""
    if changed not in PROCESS_EVENT_TAGS:
        return
    message = format_process_snapshot(snapshot, changed)
    opcua_logger.info(message)
    autogas_logger.info(message)
