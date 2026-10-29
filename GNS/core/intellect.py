"""Клиент системы распознавания номеров «Интеллект»."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional

import requests
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger('intellect')

"""
Номера серверов «Интеллект»:
    - Камера 23 (ЖД Весовая) -> "id": "1", direction = 3 - направо, 4 - налево
    - Камера 25 (Весовая автотранспорта 1) -> "id": "2"
    - Камера 26 (Весовая автотранспорта 2) -> "id": "3"
    - Камера 27 (Распознавание номеров КПП Выезд) -> "id": "4", direction = 1 - от камеры, 2 - к камере
    - Камера 28 (Распознавание номеров КПП Въезд) -> "id": "5", direction = 1 - от камеры, 2 - к камере
"""
RAILWAY_CAMERA = {
    'id': '1',
    'delta_minutes': 10,
}
AUTOGAS_CAMERAS = {
    'id': '2,3',
    'delta_minutes': 180,
}
KPP_CAMERAS = {
    'id': '4,5',
    'delta_minutes': 5,
}


def get_intellect_data(data) -> list:
    """
    Посылает запрос в «Интеллект» и возвращает список протоколов.

    data: словарь с данными для запроса.
    return: список словарей при успешном запросе; пустой список при ошибке.
    """
    try:
        intellect_url = f'{settings.INTELLECT_SERVER_ADDRESS}/lprserver/GetProtocolNumbers'
        response = requests.post(intellect_url, json=data, timeout=2)
        response.raise_for_status()

        result = response.json()
        if result.get('Status') == 'OK':
            return result.get('Protocols', [])
        return []

    except Exception as error:
        logger.error(f'Модуль intellect. Ошибка в функции "get_intellect_data" - {error}')
        return []


def get_start_time(delta_minutes: int) -> str:
    """
    Время начала выборки протоколов для «Интеллекта».

    «Интеллект» всегда работает в UTC+0, пояс в нём сменить нельзя.
    Наше ПО — Europe/Minsk (UTC+3), поэтому от локального времени отнимаем 3 часа.
    """
    start_date = timezone.localtime() - timedelta(hours=3, minutes=delta_minutes)
    return f'{start_date.strftime("%Y-%m-%dT%H:%M:%S")}.000'


def separation_string_date(date_string: str = '') -> tuple:
    """
    Преобразует время из «Интеллекта» в кортеж строк (дата, время).

    Дополнительно прибавляем 3 часа: «Интеллект» отдаёт данные в UTC+0.
    """
    try:
        converted_time = datetime.strptime(date_string, '%d.%m.%Y %H:%M:%S') + timedelta(hours=3)
        string_date = converted_time.strftime('%Y-%m-%d')
        string_time = converted_time.strftime('%H:%M')
    except ValueError as error:
        logger.error(f'Ошибка в функции "separation_string_date" - {error}')
        raise ValueError(f'Invalid date format: {error}')
    return string_date, string_time


def get_registration_number_list(server: dict) -> list:
    """
    Формирует тело запроса к базе «Интеллект».

    Возвращает данные машин, прицепов и цистерн в виде списка словарей.
    """
    data_for_request = {
        'id': server.get('id'),
        'time_from': get_start_time(server.get('delta_minutes')),
        'validaty_from': '' if server.get('id') == '1' else '85',
    }
    return get_intellect_data(data_for_request)


def get_plate_image(plate_id):
    """Получает JPEG-кадр номера по plate_numbers.id."""
    image_url = f'{settings.INTELLECT_SERVER_ADDRESS}/lprserver/GetImage/Frames/{plate_id}'
    try:
        response = requests.get(image_url, timeout=2)
        response.raise_for_status()

        if response.headers['Content-Type'] == 'image/jpeg':
            return response.content
        return None

    except Exception as error:
        logger.error(f'Ошибка при получении изображения - {error}')
        return None


def check_on_station(transport: dict) -> Optional[bool]:
    """
    Обрабатывает направление движения, определённое «Интеллектом».

    return:
        True — транспорт въехал на территорию ГНС
        False — транспорт выехал с территории ГНС
        None — камера/направление неизвестны
    """
    camera = transport.get('camera')
    direction = transport.get('direction')

    if camera == 'Камера 27':
        if direction == '1':
            return True
        elif direction == '2':
            return False

    if camera == 'Камера 28':
        if direction == '2':
            return True
        elif direction == '1':
            return False

    if camera == 'Камера 23':
        if direction == '4':
            return True
        elif direction == '3':
            return False

    return None


def get_transport_type(registration_number: str) -> str:
    """
    Валидирует регистрационный номер и определяет вид транспорта:

    - только цифры — ж/д цистерна
    - начинается с цифры — легковая, пропускаем
    - две буквы в начале — грузовик, иначе прицеп
    """
    if registration_number.isdigit():
        return 'railway_tank'
    if registration_number[0].isdigit():
        return ''
    if len(registration_number) != 7:
        return ''
    if registration_number[0:2].isalpha():
        return 'truck'
    return 'trailer'
