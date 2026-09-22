"""Обработка OPC-событий автоколонки (создание/завершение партии)."""

from __future__ import annotations

import logging
from typing import Any, Mapping, Optional, Tuple

from django.db.models import Q

from filling_station.models import Trailer, TrailerType, Truck
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


def get_transport_numbers() -> list[str]:
    """Список номеров из Интеллекта для автовесовой."""
    try:
        transport_list = get_registration_number_list(INTELLECT_SERVER_LIST[1])
        numbers = (
            [transport['number'] for transport in transport_list]
            if transport_list
            else []
        )
        log_autogas_numbers_snapshot(numbers)
        return numbers
    except Exception as error:
        logger.error('Ошибка при получении списка номеров: %s', error, exc_info=True)
        return []


def find_transports(
    registration_numbers: list[str],
) -> Tuple[Optional[Truck], Optional[Trailer]]:
    """Находит грузовик и прицеп по списку номеров."""
    try:
        trailer_type = TrailerType.objects.get(type='Полуприцеп цистерна')
        truck = (
            Truck.objects.filter(registration_number__in=registration_numbers)
            .filter(TRUCK_TYPE_FILTER)
            .select_related('type')
            .first()
        )
        trailer = Trailer.objects.filter(
            registration_number__in=registration_numbers,
            type=trailer_type,
        ).first()
        return truck, trailer
    except Exception as error:
        logger.error('Ошибка при поиске транспорта: %s', error, exc_info=True)
        return None, None


def process_autogas_batch_create(payload: Mapping[str, Any]) -> None:
    """Создание партии по OPC-запросу request_batch_create."""
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

    registration_numbers = get_transport_numbers()
    if not registration_numbers:
        logger.warning('Список номеров пуст, партия не создана')
        return

    truck, trailer = find_transports(registration_numbers)
    if not truck:
        logger.error('Не найден подходящий грузовик')
        write_tag('autogas.stop_batch', True)
        return

    logger.debug('Грузовик: %s-%s', truck.registration_number, truck.type.type)
    if trailer:
        logger.debug('Прицеп: %s-%s', trailer.registration_number, trailer.type.type)

    try:
        create_active_batch(
            batch_type=batch_type,
            gas_type=gas_type,
            truck=truck,
            trailer=trailer,
        )
    except ActiveBatchExistsError:
        logger.error('Уже есть активная партия, новая не создана')
        write_tag('autogas.stop_batch', True)
        return
    except Exception as error:
        logger.error('Ошибка при создании партии: %s', error, exc_info=True)
        return

    capacity_value = get_truck_capacity(truck, trailer)
    if capacity_value:
        write_tag('autogas.truck_capacity', capacity_value)
    elif capacity_value is None:
        logger.warning(
            'Не удалось определить максимальную массу газа для %s',
            truck.registration_number,
        )

    write_tag('autogas.response_batch_create', True)


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
