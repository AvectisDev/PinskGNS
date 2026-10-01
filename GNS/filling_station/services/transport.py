"""Нормализация гос. номеров и поиск грузовика/прицепа по регистрационному номеру."""

from __future__ import annotations

import logging
import re
from typing import Optional, Tuple

from django.core.exceptions import ValidationError

logger = logging.getLogger('filling_station')

# Мириада (legacy): допускает кириллицу.
_BELARUS_PLATE_PATTERN = re.compile(
    r'^([A-Za-zА-Яа-яЁё]{2})(\d{4})(\d)$',
)

# Канон storage (латиница): грузовик AI00081, прицеп A3779B1.
_TRUCK_STORAGE_PATTERN = re.compile(r'^([A-Za-z]{2})(\d{4})(\d)$')
_TRAILER_STORAGE_PATTERN = re.compile(r'^([A-Za-z])(\d{4})([A-Za-z])(\d)$')

# Строгий ввод в формах (латиница + пробел + дефис).
_TRUCK_INPUT_PATTERN = re.compile(r'^([A-Za-z]{2}) (\d{4})-(\d)$')
_TRAILER_INPUT_PATTERN = re.compile(r'^([A-Za-z]) (\d{4})([A-Za-z])-(\d)$')

TRUCK_INPUT_HELP = 'Формат: AH 0193-1 (латиница)'
TRAILER_INPUT_HELP = 'Формат: A 3779B-1 (латиница)'


def compact_registration_number(reg_number: str) -> str:
    """Убирает пробелы и дефисы, оставляет буквы и цифры."""
    if not reg_number:
        return ''
    return re.sub(r'[\s\-]+', '', reg_number.strip())


def to_storage(reg_number: str) -> str:
    """Канон БД / Интеллект: компактный номер в нижнем регистре (`ai00081`)."""
    return compact_registration_number(reg_number).lower()


def normalize_registration_number(reg_number: str) -> str:
    """
    Компактный номер для поиска/хранения.

    Alias для ``to_storage`` (нижний регистр).
    """
    return to_storage(reg_number)


def _format_registration_number(reg_number: str) -> str:
    """
    Формат номера для API Мириады: «АС 5512-1».
    Эквивалентные входные формы: «АС5512-1», «АС55121», «АС 5512-1», «AP71081».
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


def format_truck_display(reg_number: str) -> str:
    """Веб/формы: ``AI 0008-1``."""
    if not reg_number:
        return ''
    compact = to_storage(reg_number)
    match = _TRUCK_STORAGE_PATTERN.match(compact)
    if not match:
        return reg_number.strip()
    letters, digits, region = match.groups()
    return f'{letters.upper()} {digits}-{region}'


def format_trailer_display(reg_number: str) -> str:
    """Веб/формы: ``A 3779B-1``."""
    if not reg_number:
        return ''
    compact = to_storage(reg_number)
    match = _TRAILER_STORAGE_PATTERN.match(compact)
    if not match:
        return reg_number.strip()
    letter, digits, middle, region = match.groups()
    return f'{letter.upper()} {digits}{middle.upper()}-{region}'


def format_truck_hmi(reg_number: str) -> str:
    """OPC/HMI: ``AI0008-1`` (дефис, без пробела)."""
    if not reg_number:
        return ''
    compact = to_storage(reg_number)
    match = _TRUCK_STORAGE_PATTERN.match(compact)
    if not match:
        return compact.upper()
    letters, digits, region = match.groups()
    return f'{letters.upper()}{digits}-{region}'


def format_trailer_hmi(reg_number: str) -> str:
    """OPC/HMI: ``A3779B-1`` (дефис, без пробела)."""
    if not reg_number:
        return ''
    compact = to_storage(reg_number)
    match = _TRAILER_STORAGE_PATTERN.match(compact)
    if not match:
        return compact.upper()
    letter, digits, middle, region = match.groups()
    return f'{letter.upper()}{digits}{middle.upper()}-{region}'


def validate_truck_input(reg_number: str) -> str:
    """
    Строгий ввод грузовика ``AH 0193-1`` (латиница).

    Returns:
        storage-значение ``ah01931``.
    """
    value = (reg_number or '').strip()
    match = _TRUCK_INPUT_PATTERN.match(value)
    if not match:
        raise ValidationError(
            f'Введите номер грузовика в формате AH 0193-1 (латиница). Получено: «{value}»'
        )
    letters, digits, region = match.groups()
    return to_storage(f'{letters}{digits}{region}')


def validate_trailer_input(reg_number: str) -> str:
    """
    Строгий ввод прицепа ``A 3779B-1`` (латиница).

    Returns:
        storage-значение ``a3779b1``.
    """
    value = (reg_number or '').strip()
    match = _TRAILER_INPUT_PATTERN.match(value)
    if not match:
        raise ValidationError(
            f'Введите номер прицепа в формате A 3779B-1 (латиница). Получено: «{value}»'
        )
    letter, digits, middle, region = match.groups()
    return to_storage(f'{letter}{digits}{middle}{region}')


def find_transport_by_registration_number(reg_number: str) -> Tuple[Optional['Truck'], Optional['Trailer']]:
    """
    Находит грузовик и прицеп по регистрационному номеру.
    Номер может быть в любом допустимом виде; поиск по storage-канону.
    """
    from filling_station.models import Truck, Trailer

    if not reg_number:
        return None, None

    normalized_number = to_storage(reg_number)

    try:
        truck = Truck.objects.filter(registration_number=normalized_number).first()
        trailer = Trailer.objects.filter(registration_number=normalized_number).first()
        return truck, trailer
    except Exception as e:
        logger.error(f"Ошибка при поиске транспорта по номеру {reg_number}: {e}")
        return None, None
