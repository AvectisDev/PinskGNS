"""Нормализация гос. номеров и поиск грузовика/прицепа по регистрационному номеру."""

import logging
import re
from typing import Optional, Tuple

from filling_station.models import Truck, Trailer

logger = logging.getLogger('filling_station')

_BELARUS_PLATE_PATTERN = re.compile(
    r'^([A-Za-zА-Яа-яЁё]{2})(\d{4})(\d)$',
)


def compact_registration_number(reg_number: str) -> str:
    """
    Убирает пробелы и дефисы, оставляет буквы и цифры.

    Args:
        reg_number (str): исходный регистрационный номер.

    Returns:
        str: компактный номер без пробелов и дефисов (или пустая строка).
    """
    if not reg_number:
        return ''
    return re.sub(r'[\s\-]+', '', reg_number.strip())


def normalize_registration_number(reg_number: str) -> str:
    """
    Преобразует номер машины в компактный формат «AM78812» (без пробелов и дефисов).
    «AM 7881-2», «AM7881-2» и «AM78812» дают один результат.

    Args:
        reg_number (str): регистрационный номер в любом допустимом виде.

    Returns:
        str: нормализованный компактный номер.
    """
    return compact_registration_number(reg_number)


def _format_registration_number(reg_number: str) -> str:
    """
    Формат номера для API Мириады: «АС 5512-1».
    Эквивалентные входные формы: «АС5512-1», «АС55121», «АС 5512-1», «AP71081».

    Args:
        reg_number (str): регистрационный номер.

    Returns:
        str: номер в формате «ББ NNNN-R» или исходное значение.
    """
    if not reg_number:
        return reg_number

    compact = compact_registration_number(reg_number)
    match = _BELARUS_PLATE_PATTERN.match(compact)
    if match:
        letters, digits, region = match.groups()
        return f'{letters.upper()} {digits}-{region}'

    if len(compact) >= 7:
        return f'{compact[:2].upper()} {compact[2:6]}-{compact[6]}'

    return reg_number.strip()


def find_transport_by_registration_number(reg_number: str) -> Tuple[Optional[Truck], Optional[Trailer]]:
    """
    Находит грузовик и прицеп по регистрационному номеру.
    Номер может быть в формате "AM 7881-2" или "AM78812".

    Args:
        reg_number (str): регистрационный номер транспорта.

    Returns:
        tuple[Truck | None, Trailer | None]: найденные объекты или (None, None).
    """
    if not reg_number:
        return None, None

    normalized_number = normalize_registration_number(reg_number)

    try:
        truck = Truck.objects.filter(registration_number=normalized_number).first()
        trailer = Trailer.objects.filter(registration_number=normalized_number).first()
        return truck, trailer
    except Exception as e:
        logger.error(f"Ошибка при поиске транспорта по номеру {reg_number}: {e}")
        return None, None
