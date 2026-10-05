"""Нормализация гос. номеров и поиск грузовика/прицепа по регистрационному номеру."""

from __future__ import annotations

import logging
import re
from typing import Optional, Tuple

from django.core.exceptions import ValidationError

logger = logging.getLogger('filling_station')

# Компакт (Интеллект): грузовик AI00081, прицеп A3779B1.
_TRUCK_COMPACT_PATTERN = re.compile(r'^([A-Za-z]{2})(\d{4})(\d)$')
_TRAILER_COMPACT_PATTERN = re.compile(r'^([A-Za-z])(\d{4})([A-Za-z])(\d)$')

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


def canonicalize_registration_number(reg_number: str) -> str:
    """
    Канон БД / веб: ``AI 0008-1`` (грузовик) или ``A 3779B-1`` (прицеп).

    Принимает компакт Интеллекта, HMI без пробела или уже каноническую строку.
    Если шаблон не распознан — возвращает исходную строку (служебные записи).
    """
    if not reg_number:
        return ''
    original = reg_number.strip()
    compact = compact_registration_number(original)
    if not compact:
        return original

    truck = _TRUCK_COMPACT_PATTERN.match(compact)
    if truck:
        letters, digits, region = truck.groups()
        return f'{letters.upper()} {digits}-{region}'

    trailer = _TRAILER_COMPACT_PATTERN.match(compact)
    if trailer:
        letter, digits, middle, region = trailer.groups()
        return f'{letter.upper()} {digits}{middle.upper()}-{region}'

    return original


def format_truck_hmi(reg_number: str) -> str:
    """OPC/HMI: ``AI0008-1`` (дефис, без пробела)."""
    if not reg_number:
        return ''
    compact = compact_registration_number(reg_number)
    match = _TRUCK_COMPACT_PATTERN.match(compact)
    if not match:
        return compact.upper() or reg_number.strip()
    letters, digits, region = match.groups()
    return f'{letters.upper()}{digits}-{region}'


def format_trailer_hmi(reg_number: str) -> str:
    """OPC/HMI: ``A3779B-1`` (дефис, без пробела)."""
    if not reg_number:
        return ''
    compact = compact_registration_number(reg_number)
    match = _TRAILER_COMPACT_PATTERN.match(compact)
    if not match:
        return compact.upper() or reg_number.strip()
    letter, digits, middle, region = match.groups()
    return f'{letter.upper()}{digits}{middle.upper()}-{region}'


def validate_truck_input(reg_number: str) -> str:
    """
    Строгий ввод грузовика ``AH 0193-1`` (латиница).

    Returns:
        канон БД ``AH 0193-1``.
    """
    value = (reg_number or '').strip()
    match = _TRUCK_INPUT_PATTERN.match(value)
    if not match:
        raise ValidationError(
            f'Введите номер грузовика в формате AH 0193-1 (латиница). Получено: «{value}»'
        )
    letters, digits, region = match.groups()
    return f'{letters.upper()} {digits}-{region}'


def validate_trailer_input(reg_number: str) -> str:
    """
    Строгий ввод прицепа ``A 3779B-1`` (латиница).

    Returns:
        канон БД ``A 3779B-1``.
    """
    value = (reg_number or '').strip()
    match = _TRAILER_INPUT_PATTERN.match(value)
    if not match:
        raise ValidationError(
            f'Введите номер прицепа в формате A 3779B-1 (латиница). Получено: «{value}»'
        )
    letter, digits, middle, region = match.groups()
    return f'{letter.upper()} {digits}{middle.upper()}-{region}'


def find_transport_by_registration_number(reg_number: str) -> Tuple[Optional['Truck'], Optional['Trailer']]:
    """
    Находит грузовик и прицеп по регистрационному номеру.
    Номер с камеры/HMI приводится к канону БД перед поиском.
    """
    from filling_station.models import Truck, Trailer

    if not reg_number:
        return None, None

    canonical = canonicalize_registration_number(reg_number)

    try:
        truck = Truck.objects.filter(registration_number=canonical).first()
        trailer = Trailer.objects.filter(registration_number=canonical).first()
        return truck, trailer
    except Exception as e:
        logger.error(f"Ошибка при поиске транспорта по номеру {reg_number}: {e}")
        return None, None
