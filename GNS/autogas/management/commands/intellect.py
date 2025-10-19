from typing import Optional
import requests
import logging
from datetime import datetime, timedelta
from django.conf import settings


logger = logging.getLogger('autogas')

"""
Номера серверов "Интеллект":
    - Камера 23 (ЖД Весовая) -> "id": "1", direction = 3 - направо, 4 - налево
    - Камера 25 (Весовая автотранспорта 1) -> "id": "2"
    - Камера 26 (Весовая автотранспорта 2) -> "id": "3"
    - Камера 27 (Распознавание номеров КПП Выезд) -> "id": "4", direction = 1 - от камеры, 2 - к камере
    - Камера 28 (Распознавание номеров КПП Въезд) -> "id": "5", direction = 1 - от камеры, 2 - к камере
"""
INTELLECT_SERVER_LIST = [
    {
        'id': '1',
        'delta_minutes': 10
    },
    {
        'id': '2,3',
        'delta_minutes': 90
    },
    {
        'id': '4,5',
        'delta_minutes': 5
    }
]

def get_intellect_data(data) -> list:
    """
    Функция посылает запрос в "Интеллект" и возвращает статус запроса и список словарей с записями о транспорте.
    data: словарь с данными для запроса.
    return: JSON-ответ в виде списка при успешном запросе; пустой список при ошибке.
    """
    try:
        intellect_url = f'{settings.INTELLECT_SERVER_ADDRESS}/lprserver/GetProtocolNumbers'
        response = requests.post(intellect_url, json=data, timeout=2)
        response.raise_for_status()

        result = response.json()
        if result['Status'] == "OK":
            item_list = result.get('Protocols', [])
            return item_list
        return []

    except Exception as error:
        logger.error(f'Модуль intellect. Ошибка в функции "get_intellect_data" - {error}')
        return []


def get_start_time(delta_minutes: int) -> str:
    """
    Функция определяет время, начиная с которого нужно запросить данные в базе данных "Интеллект".
    delta_minutes: числовое значение количества минут, которые будут отниматься от текущего времени.
    Дополнительно нужно отнять 3 часа, т.к. "Интеллект" выдаёт данные по часовому поясу UTC+0
    return: string - для передачи в формате JSON объект времени конвертируется в строку под формат "Интеллект"
    """
    start_date = datetime.now() - timedelta(hours=3, minutes=delta_minutes)
    start_date_string = f'{start_date.strftime("%Y-%m-%dT%H:%M:%S")}.000'
    return start_date_string


def separation_string_date(date_string: str = '') -> tuple:
    """
    Функция преобразует время, полученное из "Интеллект", в кортеж строк (дата, время) для передачи в JSON
    Дополнительно нужно прибавить 3 часа, т.к. "Интеллект" выдаёт данные по часовому поясу UTC+0
    time_string: строчное представление времени, полученное из "Интеллект"
    return: кортеж из строк - (дата, время)
    """
    try:
        converted_time = datetime.strptime(date_string, "%d.%m.%Y %H:%M:%S") + timedelta(hours=3)
        string_date = converted_time.strftime("%Y-%m-%d")
        string_time = converted_time.strftime("%H:%M")
    except ValueError as error:
        logger.error(f'Ошибка в функции "separation_string_date" - {error}')
        raise ValueError(f"Invalid date format: {error}")
    return string_date, string_time


def get_registration_number_list(server: dict) -> list:
    """
    Функция формирует тело запроса к базе данных "Интеллект".
    Возвращает данные машин, прицепов и цистерн в виде списка словарей.
    """

    data_for_request = {
        "id": server.get('id'),
        "time_from": get_start_time(server.get('delta_minutes')),
        "validaty_from": "" if server.get('id') == '1' else "85"
    }
    return get_intellect_data(data_for_request)


def check_on_station(transport: dict) -> Optional[bool]:
    """
    Функция обрабатывает направление движения транспорта, определённое "Интеллектом", и возвращает статус
    return:
        True - транспорт въёхал на территорию ГНС
        False - транспорт выехал с территории ГНС
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


def get_transport_type(registration_number: str) -> str:
    """
    Функция валидирует регистрационный номер транспорта и определяет вид транспорта:
    - если номер состоит из цифр, значит это жд цистерна
    - если в номере есть буквы и он начинается с цифры, значит это легковая машина - пропускаем обработку
    - если номер начинается с 2-х букв, значит это грузовик, иначе - прицеп
    """
    if registration_number.isdigit():
        return 'railway_tank'
    if registration_number[0].isdigit():
        return ''
    if len(registration_number) != 7:
        return ''
    if registration_number[0:2].isalpha():
        return 'truck'
    else:
        return 'trailer'
