from __future__ import annotations

import logging
from typing import Any, Mapping, Optional, Union

from django.core.cache import cache
from django.utils import timezone

from filling_station.models import Trailer, Truck
from transport.management.commands.intellect import check_on_station

logger = logging.getLogger('kpp')

CACHE_TIMEOUT = 300
Vehicle = Union[Truck, Trailer]


def _event_cache_key(registration_number: str, is_on_station: bool) -> str:
    return f'kpp:{registration_number}:{int(is_on_station)}'


def find_vehicle(registration_number: str) -> Optional[Vehicle]:
    truck = Truck.objects.filter(registration_number=registration_number).first()
    trailer = Trailer.objects.filter(registration_number=registration_number).first()
    if truck and trailer:
        logger.warning(
            f'КПП. Номер {registration_number} найден и у грузовика, и у прицепа, '
            f'используется грузовик id={truck.pk}'
        )
        return truck
    return truck or trailer


def apply_station_status(vehicle: Vehicle, is_on_station: bool) -> bool:
    """
    Обновляет статус только при реальной смене.
    Возвращает True, если запись изменилась.
    """
    if vehicle.is_on_station == is_on_station:
        return False

    now = timezone.now()
    if is_on_station:
        vehicle.is_on_station = True
        vehicle.entry_at = now
        vehicle.departure_at = None
        vehicle.save(update_fields=['is_on_station', 'entry_at', 'departure_at'])
    else:
        vehicle.is_on_station = False
        vehicle.departure_at = now
        vehicle.save(update_fields=['is_on_station', 'departure_at'])
    return True


def process_kpp_event(transport: Mapping[str, Any]) -> None:
    registration_number = (transport.get('number') or '').strip()
    if not registration_number:
        logger.warning('КПП. Пропуск записи без регистрационного номера')
        return

    is_on_station = check_on_station(dict(transport))
    if is_on_station is None:
        logger.warning(
            f'КПП. Неизвестное направление для {registration_number}: '
            f'camera={transport.get("camera")}, direction={transport.get("direction")}'
        )
        return

    cache_key = _event_cache_key(registration_number, is_on_station)
    if cache.get(cache_key):
        logger.debug(
            f'КПП. Номер {registration_number} с направлением '
            f'{"въезд" if is_on_station else "выезд"} уже обрабатывался'
        )
        return

    vehicle = find_vehicle(registration_number)
    if vehicle is None:
        logger.error(f'КПП. Транспорт с номером {registration_number} не найден')
        return

    changed = apply_station_status(vehicle, is_on_station)
    cache.set(cache_key, True, CACHE_TIMEOUT)
    logger.info(
        f'КПП. Обработка завершена. '
        f'{"Грузовик" if isinstance(vehicle, Truck) else "Прицеп"} '
        f'№ {registration_number}, '
        f'{"въезд" if is_on_station else "выезд"}'
        f'{"" if changed else ", статус без изменений"}'
    )


def process_kpp_events(transport_list: list[Mapping[str, Any]]) -> None:
    for transport in transport_list:
        try:
            process_kpp_event(transport)
        except Exception as error:
            logger.error(
                f'КПП. Ошибка обработки записи {transport}: {error}',
                exc_info=True,
            )


def close_all_on_station() -> tuple[int, int]:
    now = timezone.now()
    trucks = Truck.objects.filter(is_on_station=True).update(
        is_on_station=False,
        departure_at=now,
    )
    trailers = Trailer.objects.filter(is_on_station=True).update(
        is_on_station=False,
        departure_at=now,
    )
    return trucks, trailers
