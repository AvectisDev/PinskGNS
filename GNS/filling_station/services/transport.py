import logging
from typing import Optional, Tuple

from filling_station.models import Truck, Trailer

logger = logging.getLogger('filling_station')


def normalize_registration_number(reg_number: str) -> str:
    """
    Преобразует номер машины из формата "AM 7881-2" в формат "AM78812" (убирает пробелы и дефис).
    Args:
        reg_number (str): Номер машины в формате "AM 7881-2"
    Returns:
        str: Номер машины в формате "AM78812"
    """
    if not reg_number:
        return ''
    return reg_number.replace(' ', '').replace('-', '')


def find_transport_by_registration_number(reg_number: str) -> Tuple[Optional[Truck], Optional[Trailer]]:
    """
    Находит грузовик и прицеп по регистрационному номеру.
    Номер может быть в формате "AM 7881-2" или "AM78812".
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
