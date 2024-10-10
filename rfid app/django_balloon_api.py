import aiohttp
import asyncio

BASE_URL = "http://10.10.12.253:8000/api"  # server address
USERNAME = "reader"
PASSWORD = "rfid-device"


async def get_balloon(nfc_tag):
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(f"{BASE_URL}/balloon-passport?nfc_tag={nfc_tag}", timeout=3,
                                   auth=aiohttp.BasicAuth(USERNAME, PASSWORD)) as response:

                response.raise_for_status()  # Поднимает исключение для 4xx и 5xx
                return await response.json()

        except (aiohttp.ClientError, asyncio.TimeoutError) as error:
            print(f'get_balloon function error: {error}')
            return None


async def create_balloon(data):
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(f"{BASE_URL}/balloon-passport", json=data, timeout=3,
                                    auth=aiohttp.BasicAuth(USERNAME, PASSWORD)) as response:
                response.raise_for_status()  # Поднимает исключение для 4xx и 5xx
                return await response.json()

        except (aiohttp.ClientError, asyncio.TimeoutError) as error:
            print(f'create_balloon function error: {error}')
            return None


async def update_balloon(nfc_tag, data):
    async with aiohttp.ClientSession() as session:
        try:
            async with session.patch(f"{BASE_URL}/balloon-passport?nfc_tag={nfc_tag}", json=data, timeout=3,
                                     auth=aiohttp.BasicAuth(USERNAME, PASSWORD)) as response:
                response.raise_for_status()  # вызывает исключение для кодов ошибок HTTP
                return await response.json()

        except (aiohttp.ClientError, asyncio.TimeoutError) as error:
            print(f'update_balloon function error: {error}')
            return None


async def get_batch_balloons(batch_type: str):
    """Проверяет наличие в базе данных активных партий и возвращает признак True и данные активной партии, если
    партия есть в базе, и False - если таких партий нет.

    Args:
        batch_type (str): Тип партии для запроса.

    Returns:
        dict: (dict) - данные партии или None.
    """

    if batch_type == 'loading':
        url = f'{BASE_URL}/balloons-loading?last_active=True'
    elif batch_type == 'unloading':
        url = f'{BASE_URL}/balloons-unloading?last_active=True'
    else:
        print(f'get_batch_balloons function error: No batch type')
        return None

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, timeout=3, auth=aiohttp.BasicAuth(USERNAME, PASSWORD)) as response:
                response.raise_for_status()  # Проверка на успешный статус-код
                return await response.json()

        except (aiohttp.ClientError, asyncio.TimeoutError) as error:
            print(f'get_batch_balloons function error: {error}')
            return None
        except ValueError as error:  # Обработка ошибок кода JSON
            print(f'get_batch_balloons function error: {error}')
            return None


async def add_balloon_to_batch(reader: dict):
    batch_type = reader['function']

    if batch_type == 'loading':
        url = f'{BASE_URL}/balloons-loading/add-balloon'
    elif batch_type == 'unloading':
        url = f'{BASE_URL}/balloons-unloading/add-balloon'
    else:
        print(f'get_batch_balloons function error: No batch type')
        return None

    data = {
        'id': reader['batch']['batch_id'],
        'balloon_id': reader['batch']['balloon_id']
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.patch(url, json=data, timeout=3, auth=aiohttp.BasicAuth(USERNAME, PASSWORD)) as response:
                response.raise_for_status()  # Поднимает исключение для 4xx и 5xx
                return response.status

        except (aiohttp.ClientError, asyncio.TimeoutError) as error:
            print(f'update_batch_balloons function error: {error}')
            return None
        except ValueError as error:  # Обработка ошибок кода JSON
            print(f'update_batch_balloons function error: {error}')
            return None
        except KeyError as error:
            print(f'update_batch_balloons function error: {error}')
            return None
