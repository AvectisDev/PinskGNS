"""Обработка OPC-событий автоколонки (propose/list/confirm/завершение)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Mapping, Optional, Sequence, Tuple

from django.db.models import Case, IntegerField, Q, Value, When

from filling_station.models import Trailer, Truck
from filling_station.services.transport import (
    format_trailer_hmi,
    format_truck_hmi,
    to_storage,
)
from opcua.api import write_tag
from autogas.management.commands.intellect import (
    INTELLECT_SERVER_LIST,
    get_registration_number_list,
)
from autogas.services import (
    ActiveBatchExistsError,
    NoActiveBatchError,
    complete_active_batch,
    create_active_batch,
    get_truck_capacity,
    log_autogas_batch_status,
    log_autogas_numbers_snapshot,
    resolve_batch_type,
    resolve_gas_type,
)

logger = logging.getLogger('autogas')

TRUCK_TYPE_FILTER = Q(type__type='Цистерна') | Q(type__type='Седельный тягач')
TRAILER_TYPE_NAME = 'Полуприцеп цистерна'
VEHICLE_LIST_SIZE = 10
DISPLAY_MAX_LEN = 32


@dataclass(frozen=True)
class VehicleCombo:
    """Связка тягач/цистерна (+ прицеп при наличии) для HMI."""

    truck: Truck
    trailer: Optional[Trailer] = None

    @property
    def on_station_rank(self) -> int:
        if self.truck.is_on_station:
            return 1
        if self.trailer and self.trailer.is_on_station:
            return 1
        return 0


def format_list_line(index: int, combo: VehicleCombo) -> str:
    """Строка vehicle_list_i: «N    truck    [trailer]» (N — 1-based, HMI-формат)."""
    n = index + 1
    truck_no = format_truck_hmi(combo.truck.registration_number)
    if combo.trailer:
        trailer_no = format_trailer_hmi(combo.trailer.registration_number)
        text = f'{n}    {truck_no}    {trailer_no}'
    else:
        text = f'{n}    {truck_no}'
    return text[:DISPLAY_MAX_LEN]


def parse_vehicle_list_line(line: Any) -> Tuple[Optional[str], Optional[str]]:
    """Разбор строки списка → (truck_number, trailer_number|None) в storage."""
    if line is None:
        return None, None
    parts = str(line).split()
    if len(parts) < 2:
        return None, None
    truck_no = to_storage(parts[1]) or None
    trailer_no = to_storage(parts[2]) if len(parts) >= 3 else None
    return truck_no, trailer_no or None


def get_transport_numbers() -> list[str]:
    """Список номеров из Интеллекта для автовесовой (storage-канон)."""
    try:
        transport_list = get_registration_number_list(INTELLECT_SERVER_LIST[1])
        numbers = (
            [to_storage(transport['number']) for transport in transport_list if transport.get('number')]
            if transport_list
            else []
        )
        numbers = [n for n in numbers if n]
        log_autogas_numbers_snapshot(numbers)
        return numbers
    except Exception as error:
        logger.error('Ошибка при получении списка номеров: %s', error, exc_info=True)
        return []


def _linked_gas_trailer(truck: Truck) -> Optional[Trailer]:
    """Активный полуприцеп-цистерна, привязанный к тягачу."""
    return (
        Trailer.objects
        .filter(
            truck=truck,
            type__type=TRAILER_TYPE_NAME,
            is_active=True,
        )
        .select_related('type')
        .first()
    )


def find_transports(
    registration_numbers: list[str],
) -> Tuple[Optional[Truck], Optional[Trailer]]:
    """Находит активный грузовик и прицеп по списку номеров."""
    try:
        storage_numbers = [to_storage(n) for n in registration_numbers if n]
        storage_numbers = [n for n in storage_numbers if n]
        if not storage_numbers:
            return None, None

        truck = (
            Truck.objects.filter(
                registration_number__in=storage_numbers,
                is_active=True,
            )
            .filter(TRUCK_TYPE_FILTER)
            .select_related('type')
            .first()
        )
        if truck is None:
            return None, None

        trailer = Trailer.objects.filter(
            registration_number__in=storage_numbers,
            type__type=TRAILER_TYPE_NAME,
            is_active=True,
        ).select_related('type').first()

        if truck.type.type == 'Седельный тягач':
            if trailer is None or trailer.truck_id != truck.pk:
                trailer = _linked_gas_trailer(truck)
            if trailer is None:
                return None, None
        elif truck.type.type == 'Цистерна':
            trailer = None

        return truck, trailer
    except Exception as error:
        logger.error('Ошибка при поиске транспорта: %s', error, exc_info=True)
        return None, None


def find_on_station_combo() -> Optional[VehicleCombo]:
    """Fallback: активный транспорт нужного типа на станции."""
    cistern = (
        Truck.objects
        .filter(type__type='Цистерна', is_active=True, is_on_station=True)
        .select_related('type')
        .order_by('registration_number')
        .first()
    )
    if cistern:
        return VehicleCombo(truck=cistern)

    tractor = (
        Truck.objects
        .filter(type__type='Седельный тягач', is_active=True, is_on_station=True)
        .select_related('type')
        .order_by('registration_number')
        .first()
    )
    if tractor:
        trailer = _linked_gas_trailer(tractor)
        if trailer:
            return VehicleCombo(truck=tractor, trailer=trailer)

    trailer_on_station = (
        Trailer.objects
        .filter(
            type__type=TRAILER_TYPE_NAME,
            is_active=True,
            is_on_station=True,
            truck__type__type='Седельный тягач',
            truck__is_active=True,
        )
        .select_related('truck', 'truck__type', 'type')
        .order_by('registration_number')
        .first()
    )
    if trailer_on_station:
        return VehicleCombo(truck=trailer_on_station.truck, trailer=trailer_on_station)

    return None


def build_manual_vehicle_list() -> list[VehicleCombo]:
    """До 10 связок для ручного выбора на HMI."""
    combos: list[VehicleCombo] = []

    cisterns = (
        Truck.objects
        .filter(type__type='Цистерна', is_active=True)
        .select_related('type')
        .annotate(
            on_station_rank=Case(
                When(is_on_station=True, then=Value(1)),
                default=Value(0),
                output_field=IntegerField(),
            )
        )
        .order_by('-on_station_rank', 'registration_number')
    )
    for truck in cisterns:
        combos.append(VehicleCombo(truck=truck))

    trailers = (
        Trailer.objects
        .filter(
            type__type=TRAILER_TYPE_NAME,
            is_active=True,
            truck__type__type='Седельный тягач',
            truck__is_active=True,
        )
        .select_related('truck', 'truck__type', 'type')
        .annotate(
            on_station_rank=Case(
                When(Q(is_on_station=True) | Q(truck__is_on_station=True), then=Value(1)),
                default=Value(0),
                output_field=IntegerField(),
            )
        )
        .order_by('-on_station_rank', 'truck__registration_number', 'registration_number')
    )
    for trailer in trailers:
        combos.append(VehicleCombo(truck=trailer.truck, trailer=trailer))

    combos.sort(
        key=lambda c: (
            -c.on_station_rank,
            c.truck.registration_number,
            c.trailer.registration_number if c.trailer else '',
        )
    )
    return combos[:VEHICLE_LIST_SIZE]


def combo_from_numbers(
    truck_number: Any,
    trailer_number: Any = None,
) -> Optional[VehicleCombo]:
    """Резолв связки по предложенным номерам с HMI."""
    truck_no = to_storage(str(truck_number)) if truck_number is not None else ''
    if not truck_no:
        return None
    numbers = [truck_no]
    trailer_no = to_storage(str(trailer_number)) if trailer_number is not None else ''
    if trailer_no:
        numbers.append(trailer_no)
    truck, trailer = find_transports(numbers)
    if truck is None:
        return None
    return VehicleCombo(truck=truck, trailer=trailer)


def combo_from_list_selection(payload: Mapping[str, Any]) -> Optional[VehicleCombo]:
    """Связка из vehicle_list_[selected_vehicle_index] (list_mode, без пересборки БД)."""
    try:
        idx = int(payload.get('selected_vehicle_index'))
    except (TypeError, ValueError):
        return None
    if idx < 0 or idx >= VEHICLE_LIST_SIZE:
        return None
    truck_no, trailer_no = parse_vehicle_list_line(payload.get(f'vehicle_list_{idx}'))
    if not truck_no:
        return None
    return combo_from_numbers(truck_no, trailer_no)


def _write_propose(combo: VehicleCombo) -> None:
    write_tag(
        'autogas.vehicle_select.proposed_truck_number',
        format_truck_hmi(combo.truck.registration_number),
    )
    write_tag(
        'autogas.vehicle_select.proposed_trailer_number',
        format_trailer_hmi(combo.trailer.registration_number) if combo.trailer else '',
    )
    write_tag('autogas.vehicle_select.proposed_ready', True)
    for i in range(VEHICLE_LIST_SIZE):
        write_tag(f'autogas.vehicle_select.vehicle_list_{i}', '')


def _write_manual_list(combos: Sequence[VehicleCombo]) -> None:
    write_tag('autogas.vehicle_select.proposed_ready', False)
    write_tag('autogas.vehicle_select.proposed_truck_number', '')
    write_tag('autogas.vehicle_select.proposed_trailer_number', '')
    for i in range(VEHICLE_LIST_SIZE):
        text = format_list_line(i, combos[i]) if i < len(combos) else ''
        write_tag(f'autogas.vehicle_select.vehicle_list_{i}', text)


def _clear_vehicle_select_ui(*, keep_propose: bool = False) -> None:
    write_tag('autogas.vehicle_select.operator_confirm', False)
    write_tag('autogas.vehicle_select.selected_vehicle_index', -1)
    if keep_propose:
        return
    write_tag('autogas.vehicle_select.proposed_ready', False)
    write_tag('autogas.vehicle_select.proposed_truck_number', '')
    write_tag('autogas.vehicle_select.proposed_trailer_number', '')
    for i in range(VEHICLE_LIST_SIZE):
        write_tag(f'autogas.vehicle_select.vehicle_list_{i}', '')


def _ack_batch_created(truck: Truck, trailer: Optional[Trailer]) -> None:
    capacity_value = get_truck_capacity(truck, trailer)
    if capacity_value:
        write_tag('autogas.truck_capacity', capacity_value)
    elif capacity_value is None:
        logger.warning(
            'Не удалось определить максимальную массу газа для %s',
            truck.registration_number,
        )
    write_tag('autogas.response_batch_create', True)
    _clear_vehicle_select_ui()


def process_autogas_batch_create(payload: Mapping[str, Any]) -> None:
    """
    Шаг 2: запрос номера — propose или сразу ручной список.
    Партия в БД здесь не создаётся.
    """
    log_autogas_batch_status({
        'batch_type_code': payload.get('batch_type_code'),
        'gas_type': payload.get('gas_type'),
        'request_batch_create': payload.get('request_batch_create'),
        'request_batch_complete': False,
    })

    batch_type_code = payload.get('batch_type_code')
    gas_type_code = payload.get('gas_type')

    batch_type = resolve_batch_type(batch_type_code)
    if batch_type is None:
        logger.error('Неизвестный тип партии: %s', batch_type_code)
        write_tag('autogas.stop_batch', True)
        return

    gas_type = resolve_gas_type(gas_type_code)
    if gas_type is None:
        logger.error('Неизвестный тип газа: %s', gas_type_code)
        write_tag('autogas.stop_batch', True)
        return

    combo: Optional[VehicleCombo] = None
    registration_numbers = get_transport_numbers()
    if registration_numbers:
        truck, trailer = find_transports(registration_numbers)
        if truck:
            combo = VehicleCombo(truck=truck, trailer=trailer)

    if combo is None:
        combo = find_on_station_combo()

    if combo is not None:
        logger.debug(
            'Propose: %s%s',
            combo.truck.registration_number,
            f' / {combo.trailer.registration_number}' if combo.trailer else '',
        )
        _write_propose(combo)
        return

    combos = build_manual_vehicle_list()
    logger.warning(
        'Автоопределение не удалось, выгружен ручной список (%s шт.)',
        len(combos),
    )
    _write_manual_list(combos)


def process_autogas_operator_confirm(payload: Mapping[str, Any]) -> None:
    """Confirm на GS21 → create_active_batch + response_number_detect."""
    log_autogas_batch_status({
        'batch_type_code': payload.get('batch_type_code'),
        'gas_type': payload.get('gas_type'),
        'request_batch_create': payload.get('request_batch_create'),
        'request_batch_complete': False,
        'operator_confirm': True,
    })

    if not payload.get('request_batch_create'):
        logger.warning('operator_confirm без request_number_identification — игнор')
        write_tag('autogas.vehicle_select.operator_confirm', False)
        return

    if payload.get('response_batch_create'):
        logger.debug('Партия уже подтверждена, повторный confirm игнорируем')
        write_tag('autogas.vehicle_select.operator_confirm', False)
        return

    batch_type = resolve_batch_type(payload.get('batch_type_code'))
    gas_type = resolve_gas_type(payload.get('gas_type'))
    if batch_type is None or gas_type is None:
        logger.error(
            'Confirm: неизвестный тип партии/газа: %s / %s',
            payload.get('batch_type_code'),
            payload.get('gas_type'),
        )
        write_tag('autogas.stop_batch', True)
        write_tag('autogas.vehicle_select.operator_confirm', False)
        return

    list_mode = bool(payload.get('list_mode'))
    if list_mode:
        combo = combo_from_list_selection(payload)
    else:
        combo = combo_from_numbers(
            payload.get('proposed_truck_number'),
            payload.get('proposed_trailer_number'),
        )

    if combo is None:
        logger.error('Confirm: не удалось определить транспорт')
        write_tag('autogas.vehicle_select.operator_confirm', False)
        return

    try:
        create_active_batch(
            batch_type=batch_type,
            gas_type=gas_type,
            truck=combo.truck,
            trailer=combo.trailer,
        )
    except ActiveBatchExistsError:
        logger.error('Уже есть активная партия, новая не создана')
        write_tag('autogas.stop_batch', True)
        write_tag('autogas.vehicle_select.operator_confirm', False)
        return
    except Exception as error:
        logger.error('Ошибка при создании партии: %s', error, exc_info=True)
        write_tag('autogas.vehicle_select.operator_confirm', False)
        return

    logger.debug(
        'Партия создана по Confirm: %s%s',
        combo.truck.registration_number,
        f' / {combo.trailer.registration_number}' if combo.trailer else '',
    )
    _ack_batch_created(combo.truck, combo.trailer)


def process_autogas_batch_complete(payload: Mapping[str, Any]) -> None:
    """Завершение активной партии по OPC-запросу request_batch_complete."""
    log_autogas_batch_status({
        'batch_type_code': None,
        'gas_type': None,
        'request_batch_create': False,
        'request_batch_complete': payload.get('request_batch_complete'),
    })
    try:
        complete_active_batch(payload)
        write_tag('autogas.response_batch_complete', True)
    except NoActiveBatchError:
        logger.error('Нет активной партии для завершения')
    except Exception as error:
        logger.error('Ошибка при завершении партии: %s', error, exc_info=True)
