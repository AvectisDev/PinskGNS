"""Обработка событий ЖД весовой (цистерны), вызываемая из OPC bridge."""

from __future__ import annotations

import logging
import time
from datetime import datetime
from decimal import Decimal
from typing import Any, Mapping, Optional

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import MultipleObjectsReturned
from django.core.files.base import ContentFile

from opcua.api import write_tag
from railway_service.management.commands.intellect import (
    INTELLECT_SERVER_LIST,
    get_plate_image,
    get_registration_number_list,
)
from railway_service.models import RailwayBatch, RailwayTank, RailwayTankHistory
from railway_service.services.ocryp import log_number_comparison
from railway_service.services.status_log import log_railway_tank_status

logger = logging.getLogger('railway')

LAST_TANK_NUMBER_CACHE_KEY = 'last_tank_number'
INTELLECT_DELAY_SECONDS = 2


def fetch_railway_tank_data() -> tuple[Optional[int], Optional[bytes]]:
    """Запрос в Интеллект: номер последней цистерны и фото."""
    logger.debug('Выполняется запрос к Интеллекту...')
    railway_tank_list = get_registration_number_list(INTELLECT_SERVER_LIST[0])
    if not railway_tank_list:
        logger.error('ЖД цистерна не определена')
        return None, None

    last_tank = railway_tank_list[-1]
    plate_image = last_tank.get('plate_numbers.id')
    photo_of_number = get_plate_image(plate_image) if plate_image else None
    return int(last_tank['number']), photo_of_number


def batch_process(railway_tank: RailwayTank) -> None:
    """Создаёт активную партию (если нужно) и добавляет в неё цистерну."""
    try:
        railway_batch, _batch_created = RailwayBatch.objects.get_or_create(
            is_active=True,
            defaults={'is_active': True},
        )
        railway_batch.railway_tank_list.add(railway_tank)
        logger.info(
            'Цистерна %s добавлена в партию %s',
            railway_tank.registration_number,
            railway_batch.id,
        )
    except MultipleObjectsReturned:
        logger.error('Найдено более одной активной партии')
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


def process_railway_tank_event(payload: Mapping[str, Any]) -> None:
    """
    Обработка срабатывания камеры ЖД весовой.

    Args:
        payload: снимок OPC-тегов (tank_weight, camera_worked, is_on_station).
    """
    tank_weight = payload.get('tank_weight')
    camera_worked = payload.get('camera_worked')
    is_on_station = payload.get('is_on_station')

    opc_values = (
        f'tank_weight={tank_weight}, '
        f'camera_worked={camera_worked}, '
        f'is_on_station={is_on_station}'
    )
    log_railway_tank_status(opc_values)

    if None in (tank_weight, camera_worked, is_on_station):
        logger.warning('ЖД весовая. Неполные OPC-значения, пропуск: %s', opc_values)
        return

    if not camera_worked:
        return

    logger.info(
        'Камера сработала. Вес жд цистерны %s. Цистерна на станции: %s',
        tank_weight,
        is_on_station,
    )
    write_tag('railway.camera_worked', False)

    time.sleep(INTELLECT_DELAY_SECONDS)

    registration_number, image_data = fetch_railway_tank_data()
    if not registration_number:
        logger.error('ЖД цистерна не определена — пропуск обработки')
        return

    if registration_number == cache.get(LAST_TANK_NUMBER_CACHE_KEY):
        logger.warning(
            'ЖД цистерна с номером %s уже обрабатывалась — пропуск',
            registration_number,
        )
        return

    cache.set(LAST_TANK_NUMBER_CACHE_KEY, registration_number)

    if getattr(settings, 'OCRYP_URL', ''):
        try:
            log_number_comparison(registration_number, image_data)
        except Exception as error:
            logger.error('OCR сравнение завершилось ошибкой: %s', error, exc_info=True)

    railway_tank = tank_process(
        registration_number,
        image_data,
        bool(is_on_station),
        tank_weight,
    )
    if railway_tank:
        batch_process(railway_tank)
        logger.info(
            'ЖД весовая. Обработка цистерны № %s успешно завершена',
            registration_number,
        )
