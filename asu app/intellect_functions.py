import asyncio
import aiohttp
from datetime import datetime, timedelta
from settings import INTELLECT_URL


async def get_intellect_data(data) -> list:
    """
    Функция посылает запрос в "Интеллект" и возвращает статус запроса и список словарей с записями о транспорте
    data: словарь с данными для запроса
    return: JSON-ответ в виде списка при успешном запросе;
            пустой список при ошибке
    """
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(INTELLECT_URL, json=data, timeout=5) as response:
                response.raise_for_status()  # Вызывает исключение для ошибок HTTP

                result = await response.json()

                if result['Status'] == "OK":
                    item_list = result['Protocols'] if 'Protocols' in result else []
                    return item_list
                return []

        except (aiohttp.ClientError, asyncio.TimeoutError) as error:
            print(f'get_intellect_data function error - {error}')
            return []

        except (ValueError, KeyError) as JSON_error:  # Обработка ошибок парсинга JSON и доступа к ключам
            print(f'get_intellect_data function JSON_error - {JSON_error}')
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
        raise ValueError(f"Invalid date format: {error}")
    return string_date, string_time


async def get_registration_number_list(server: dict) -> list:
    """
    Функция формирует тело запроса к базе данных "Интеллект".
    Возвращает номер и дату прибывших/убывших машин и прицепов в виде списка словарей.
    """

    data_for_request = {
        "id": server['id'],
        "time_from": get_start_time(server['delta_minutes']),
        "validaty_from": "90"
    }
    intellect_data = await get_intellect_data(data_for_request)

    out_list = []
    if len(intellect_data) > 0:

        for item in intellect_data:
            out_list.append({
                'registration_number': item['number'],
                'date': item['date'],
                'direction': item['direction'],
                "camera": item["camera"]
            })

    return out_list


def check_on_station(transport: dict) -> bool:
    """
    Функция обрабатывает направление движения транспорта, определённое "Интеллектом", и возвращает статус
    return:
        True - транспорт въёхал на территорию ГНС
        False - транспорт выехал с территории ГНС
    """
    camera = transport['camera']
    direction = transport['direction']

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
