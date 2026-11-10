"""Обработка событий ЖД весовой (цистерны), вызываемая из OPC bridge."""

from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal
from typing import Any, Mapping, Optional

from django.conf import settings
from django.core.files.base import ContentFile

from opcua.api import write_tag
from railway_service.models import RailwayBatch, RailwayTank, RailwayTankHistory
from railway_service.services.intellect_match import (
    MatchedTank,
    append_pending_weighing,
    clear_pending_weighings,
    get_pending_weighings,
    mark_protocols_seen,
    match_protocols_to_weighings,
    matched_newest_first,
    poll_new_protocols,
    set_pending_weighings,
)
from railway_service.services.ocryp import log_number_comparison
from railway_service.services.status_log import log_railway_tank_status

logger = logging.getLogger('railway')


def batch_process(railway_tank: RailwayTank) -> None:
    """Добавляет цистерну в активную партию (партия создаётся по OPC active)."""
    try:
        railway_batch = RailwayBatch.objects.filter(is_active=True).first()
        if railway_batch is None:
            logger.warning(
                'Нет активной партии — цистерна %s не добавлена',
                railway_tank.registration_number,
            )
            return
        railway_batch.railway_tank_list.add(railway_tank)
        logger.info(
            'Цистерна %s добавлена в партию %s',
            railway_tank.registration_number,
            railway_batch.id,
        )
    except Exception as error:
        logger.error('Ошибка при обработке партии: %s', error, exc_info=True)


def tank_process(
    registration_number: int,
    image_data: Optional[bytes],
    is_on_station: bool,
    tank_weight: Any,
) -> Optional[RailwayTank]:
    """Создаёт/обновляет цистерну и историческую запись."""
    try:
        railway_tank, tank_created = RailwayTank.objects.get_or_create(
            registration_number=registration_number,
            defaults={
                'registration_number': registration_number,
                'is_on_station': is_on_station,
            },
        )

        if tank_created:
            if is_on_station:
                RailwayTankHistory.objects.create(
                    tank=railway_tank,
                    arrival_at=datetime.now(),
                    full_weight=tank_weight,
                    arrival_img=(
                        ContentFile(image_data, name=f'{registration_number}_arrival.jpg')
                        if image_data
                        else None
                    ),
                )
            else:
                RailwayTankHistory.objects.create(
                    tank=railway_tank,
                    departure_at=datetime.now(),
                    empty_weight=tank_weight,
                    departure_img=(
                        ContentFile(image_data, name=f'{registration_number}_departure.jpg')
                        if image_data
                        else None
                    ),
                )
            logger.info(
                'Создана новая цистерна %s с исторической записью',
                registration_number,
            )
            return railway_tank

        railway_tank.is_on_station = is_on_station
        railway_tank.save()

        if is_on_station:
            RailwayTankHistory.objects.create(
                tank=railway_tank,
                arrival_at=datetime.now(),
                full_weight=tank_weight,
                arrival_img=(
                    ContentFile(image_data, name=f'{registration_number}_arrival.jpg')
                    if image_data
                    else None
                ),
            )
            logger.info(
                'Создана историческая запись для цистерны %s при въезде',
                registration_number,
            )
            return railway_tank

        open_hist = railway_tank.tank_history.order_by('-id').first()

        if not open_hist:
            RailwayTankHistory.objects.create(
                tank=railway_tank,
                departure_at=datetime.now(),
                empty_weight=tank_weight,
                departure_img=(
                    ContentFile(image_data, name=f'{registration_number}_departure.jpg')
                    if image_data
                    else None
                ),
            )
            logger.warning(
                'Создана историческая запись для цистерны %s при выезде (не было истории)',
                registration_number,
            )
            return railway_tank

        if open_hist.arrival_at and open_hist.departure_at:
            RailwayTankHistory.objects.create(
                tank=railway_tank,
                departure_at=datetime.now(),
                empty_weight=tank_weight,
                departure_img=(
                    ContentFile(image_data, name=f'{registration_number}_departure.jpg')
                    if image_data
                    else None
                ),
            )
            logger.warning(
                'Создана не полная историческая запись для цистерны %s при выезде',
                registration_number,
            )
            return railway_tank

        open_hist.departure_at = datetime.now()
        open_hist.empty_weight = tank_weight
        tank_weight_decimal = (
            Decimal(str(tank_weight)) if tank_weight is not None else None
        )
        open_hist.gas_weight = (
            open_hist.full_weight - tank_weight_decimal
            if open_hist.full_weight and tank_weight_decimal is not None
            else None
        )

        if image_data:
            open_hist.departure_img.save(
                f'{registration_number}_departure.jpg',
                ContentFile(image_data),
                save=False,
            )

        open_hist.save()
        logger.info(
            'Обновлена историческая запись для цистерны %s при выезде',
            registration_number,
        )
        return railway_tank

    except Exception as error:
        logger.error(
            'ЖД. Ошибка при создании/обновлении данных цистерны: %s',
            error,
            exc_info=True,
        )
        return None


def _apply_matched_tank(matched: MatchedTank) -> None:
    registration_number = matched.registration_number
    image_data = matched.image_data
    weighing = matched.weighing

    if getattr(settings, 'OCRYP_URL', ''):
        try:
            log_number_comparison(registration_number, image_data)
        except Exception as error:
            logger.error(
                'OCR сравнение завершилось ошибкой: %s',
                error,
                exc_info=True,
            )

    railway_tank = tank_process(
        registration_number,
        image_data,
        weighing.on_station,
        weighing.stable_weight,
    )
    if railway_tank:
        batch_process(railway_tank)
        logger.info(
            'ЖД весовая. Обработка цистерны № %s успешно завершена',
            registration_number,
        )


def resolve_pending_with_intellect(*, add_weighing: Optional[dict] = None) -> int:
    """
    Опрос Интеллекта с повторами и сопоставление с очередью взвешиваний.

    Args:
        add_weighing: если задан — сначала положить текущее взвешивание в очередь
            (`stable_weight`, `on_station`).

    Returns:
        Число успешно сопоставленных цистерн.
    """
    if add_weighing is not None:
        append_pending_weighing(
            stable_weight=add_weighing['stable_weight'],
            on_station=add_weighing['on_station'],
        )

    pending = get_pending_weighings()
    if not pending:
        return 0

    new_protocols = poll_new_protocols()
    matched, remaining = match_protocols_to_weighings(new_protocols, pending)
    set_pending_weighings(remaining)

    if not matched:
        logger.error(
            'ЖД цистерна не определена — взвешиваний в очереди: %s',
            len(remaining),
        )
        return 0

    mark_protocols_seen([item.protocol_id for item in matched])
    for item in matched_newest_first(matched):
        _apply_matched_tank(item)
    return len(matched)


def flush_pending_weighings_before_batch_close() -> None:
    """Добор номеров перед закрытием партии; неразобранное — в лог и очистка."""
    pending_before = get_pending_weighings()
    if not pending_before:
        return

    logger.info(
        'Закрытие партии: в очереди %s взвешиваний без номера — добор из Интеллекта',
        len(pending_before),
    )
    resolve_pending_with_intellect(add_weighing=None)
    leftover = clear_pending_weighings()
    if leftover:
        logger.error(
            'Закрытие партии: не сопоставлено взвешиваний: %s',
            [
                {
                    'stable_weight': item.stable_weight,
                    'on_station': item.on_station,
                    'captured_at': item.captured_at,
                }
                for item in leftover
            ],
        )


def process_railway_tank_event(payload: Mapping[str, Any]) -> None:
    """
    Обработка срабатывания камеры ЖД весовой.

    Args:
        payload: снимок OPC-тегов (stable_weight, camera_worked, on_station).
    """
    stable_weight = payload.get('stable_weight')
    camera_worked = payload.get('camera_worked')
    on_station = payload.get('on_station')

    opc_values = (
        f'stable_weight={stable_weight}, '
        f'camera_worked={camera_worked}, '
        f'on_station={on_station}'
    )
    log_railway_tank_status(opc_values)

    if None in (stable_weight, camera_worked, on_station):
        logger.warning('ЖД весовая. Неполные OPC-значения, пропуск: %s', opc_values)
        return

    if not camera_worked:
        return

    logger.info(
        'Камера сработала. Вес жд цистерны %s. Цистерна на станции: %s',
        stable_weight,
        on_station,
    )

    try:
        resolve_pending_with_intellect(
            add_weighing={
                'stable_weight': stable_weight,
                'on_station': bool(on_station),
            }
        )
    finally:
        # ПЛК ждёт сброс от Django после каждого цикла камеры.
        write_tag('railway.camera_worked', False)
