"""Единый реестр OPC UA тегов."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class TagDef:
    """Описание тега OPC UA."""

    name: str
    node_id: str
    domain: str


TAGS: Mapping[str, TagDef] = {
    # Railway PLC_SU1
    'railway.tank_weight': TagDef(
        name='railway.tank_weight',
        node_id='ns=4; s=Address Space.PLC_SU1.tank.stable_weight',
        domain='railway',
    ),
    'railway.camera_worked': TagDef(
        name='railway.camera_worked',
        node_id='ns=4; s=Address Space.PLC_SU1.tank.camera_worked',
        domain='railway',
    ),
    'railway.is_on_station': TagDef(
        name='railway.is_on_station',
        node_id='ns=4; s=Address Space.PLC_SU1.tank.on_station',
        domain='railway',
    ),
    # Autogas PLC_SU2
    'autogas.batch_type_code': TagDef(
        name='autogas.batch_type_code',
        node_id='ns=4; s=Address Space.PLC_SU2.batch.batch_type',
        domain='autogas',
    ),
    'autogas.gas_type': TagDef(
        name='autogas.gas_type',
        node_id='ns=4; s=Address Space.PLC_SU2.batch.gas_type',
        domain='autogas',
    ),
    'autogas.stop_batch': TagDef(
        name='autogas.stop_batch',
        node_id='ns=4; s=Address Space.PLC_SU2.batch.stop_batch',
        domain='autogas',
    ),
    'autogas.initial_mass_meter': TagDef(
        name='autogas.initial_mass_meter',
        node_id='ns=4; s=Address Space.PLC_SU2.batch.initial_mass_meter',
        domain='autogas',
    ),
    'autogas.final_mass_meter': TagDef(
        name='autogas.final_mass_meter',
        node_id='ns=4; s=Address Space.PLC_SU2.batch.final_mass_meter',
        domain='autogas',
    ),
    'autogas.gas_amount': TagDef(
        name='autogas.gas_amount',
        node_id='ns=4; s=Address Space.PLC_SU2.batch.gas_amount',
        domain='autogas',
    ),
    'autogas.truck_full_weight': TagDef(
        name='autogas.truck_full_weight',
        node_id='ns=4; s=Address Space.PLC_SU2.batch.truck_full_weight',
        domain='autogas',
    ),
    'autogas.truck_empty_weight': TagDef(
        name='autogas.truck_empty_weight',
        node_id='ns=4; s=Address Space.PLC_SU2.batch.truck_empty_weight',
        domain='autogas',
    ),
    'autogas.weight_gas_amount': TagDef(
        name='autogas.weight_gas_amount',
        node_id='ns=4; s=Address Space.PLC_SU2.batch.weight_gas_amount',
        domain='autogas',
    ),
    'autogas.truck_capacity': TagDef(
        name='autogas.truck_capacity',
        node_id='ns=4; s=Address Space.PLC_SU2.batch.truck_capacity',
        domain='autogas',
    ),
    'autogas.request_batch_create': TagDef(
        name='autogas.request_batch_create',
        node_id='ns=4; s=Address Space.PLC_SU2.batch.request_number_identification',
        domain='autogas',
    ),
    'autogas.response_batch_create': TagDef(
        name='autogas.response_batch_create',
        node_id='ns=4; s=Address Space.PLC_SU2.batch.response_number_detect',
        domain='autogas',
    ),
    'autogas.request_batch_complete': TagDef(
        name='autogas.request_batch_complete',
        node_id='ns=4; s=Address Space.PLC_SU2.batch.request_batch_complete',
        domain='autogas',
    ),
    'autogas.response_batch_complete': TagDef(
        name='autogas.response_batch_complete',
        node_id='ns=4; s=Address Space.PLC_SU2.batch.response_batch_complete',
        domain='autogas',
    ),
}


def node_id_to_name() -> dict[str, str]:
    """Обратный индекс NodeId → имя тега."""
    return {tag.node_id: tag.name for tag in TAGS.values()}
