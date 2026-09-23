"""Правила фронтов OPC → Celery tasks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence


Snapshot = Mapping[str, Any]
Condition = Callable[[Snapshot], bool]


@dataclass(frozen=True)
class TriggerDef:
    """Триггер: условие становится истинным → Celery task."""

    name: str
    task: str
    condition: Condition
    snapshot_keys: Sequence[str]
    idempotency_ttl: int = 30


def _truthy(value: Any) -> bool:
    return bool(value)


def _railway_camera_worked(snapshot: Snapshot) -> bool:
    return _truthy(snapshot.get('railway.camera_worked'))


def _autogas_create_pending(snapshot: Snapshot) -> bool:
    return (
        _truthy(snapshot.get('autogas.request_batch_create'))
        and not _truthy(snapshot.get('autogas.response_batch_create'))
        and not _truthy(snapshot.get('autogas.vehicle_select.proposed_ready'))
        and not _truthy(snapshot.get('autogas.vehicle_select.list_mode'))
    )


def _autogas_operator_confirm(snapshot: Snapshot) -> bool:
    return (
        _truthy(snapshot.get('autogas.vehicle_select.operator_confirm'))
        and _truthy(snapshot.get('autogas.request_batch_create'))
        and not _truthy(snapshot.get('autogas.response_batch_create'))
    )


def _autogas_complete_pending(snapshot: Snapshot) -> bool:
    return (
        _truthy(snapshot.get('autogas.request_batch_complete'))
        and not _truthy(snapshot.get('autogas.response_batch_complete'))
    )


TRIGGERS: tuple[TriggerDef, ...] = (
    TriggerDef(
        name='railway_camera_worked',
        task='railway_service.tasks.process_railway_tank_event',
        condition=_railway_camera_worked,
        snapshot_keys=(
            'railway.tank_weight',
            'railway.camera_worked',
            'railway.is_on_station',
        ),
        idempotency_ttl=30,
    ),
    TriggerDef(
        name='autogas_batch_create',
        task='autogas.tasks.process_autogas_batch_create',
        condition=_autogas_create_pending,
        snapshot_keys=(
            'autogas.batch_type_code',
            'autogas.gas_type',
            'autogas.request_batch_create',
            'autogas.response_batch_create',
        ),
        idempotency_ttl=30,
    ),
    TriggerDef(
        name='autogas_operator_confirm',
        task='autogas.tasks.process_autogas_operator_confirm',
        condition=_autogas_operator_confirm,
        snapshot_keys=(
            'autogas.batch_type_code',
            'autogas.gas_type',
            'autogas.request_batch_create',
            'autogas.response_batch_create',
            'autogas.vehicle_select.list_mode',
            'autogas.vehicle_select.proposed_ready',
            'autogas.vehicle_select.proposed_truck_number',
            'autogas.vehicle_select.proposed_trailer_number',
            'autogas.vehicle_select.selected_vehicle_index',
            'autogas.vehicle_select.operator_confirm',
        ),
        idempotency_ttl=30,
    ),
    TriggerDef(
        name='autogas_batch_complete',
        task='autogas.tasks.process_autogas_batch_complete',
        condition=_autogas_complete_pending,
        snapshot_keys=(
            'autogas.gas_amount',
            'autogas.truck_full_weight',
            'autogas.truck_empty_weight',
            'autogas.weight_gas_amount',
            'autogas.initial_mass_meter',
            'autogas.final_mass_meter',
            'autogas.request_batch_complete',
            'autogas.response_batch_complete',
        ),
        idempotency_ttl=30,
    ),
)


def build_payload(trigger: TriggerDef, snapshot: Snapshot) -> dict[str, Any]:
    """Собирает payload для Celery из снимка тегов (короткие ключи без префикса домена)."""
    payload: dict[str, Any] = {}
    for key in trigger.snapshot_keys:
        if key.startswith('autogas.vehicle_select.'):
            short = key[len('autogas.vehicle_select.'):]
        else:
            short = key.split('.', 1)[-1]
        payload[short] = snapshot.get(key)
    return payload
