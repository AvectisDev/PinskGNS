import aiohttp
import asyncio

BASE_URL = "http://10.10.12.253:8000/api"  # server address
USERNAME = "reader"
PASSWORD = "rfid-device"


def get_transport_path(transport_type: str):
    if transport_type == 'truck':
        return 'trucks'
    elif transport_type == 'trailer':
        return 'trailers'
    elif transport_type == 'railway_tank':
        return 'railway-tanks'
    return None


async def get_transport(number, transport_type):
    """Проверяет наличие в базе данных транспорт по указанному регистрационному номеру и возвращает данные транспорта,
    если он есть в базе, и None - если его нет.

    Args:
        number (str): регистрационный номер транспорта
        transport_type (str): тип обрабатываемой партии

    Returns:
        dict: данные транспорта в базе.
    """
    path = get_transport_path(transport_type)

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(f"{BASE_URL}/{path}?registration_number={number}", timeout=5,
                                   auth=aiohttp.BasicAuth(USERNAME, PASSWORD)) as response:
                response.raise_for_status()
                return await response.json()

        except (aiohttp.ClientError, asyncio.TimeoutError) as error:
            print(f'get_transport function error - {error}')
            return None

        except (ValueError, KeyError) as JSON_error:  # Обработка ошибок парсинга JSON и доступа к ключам
            print(f'get_transport function JSON_error - {JSON_error}')
            return None


async def create_transport(data, transport_type):
    path = get_transport_path(transport_type)

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(f"{BASE_URL}/{path}", json=data, timeout=5,
                                    auth=aiohttp.BasicAuth(USERNAME, PASSWORD)) as response:
                response.raise_for_status()  # HTTPError для ответа с кодами состояния 4xx/5xx
                return True, await response.json()

        except (aiohttp.ClientError, asyncio.TimeoutError) as error:
            print(f'create_transport function error - {error}')
            return False, error  # Возвращаем сообщение об ошибке запроса

        except (ValueError, KeyError) as JSON_error:  # Обработка ошибок парсинга JSON и доступа к ключам
            print(f'create_transport function JSON_error - {JSON_error}')
            return False, {"status": "invalid response"}


async def update_transport(data, transport_type):
    path = get_transport_path(transport_type)

    async with aiohttp.ClientSession() as session:
        try:
            async with session.patch(f"{BASE_URL}/{path}", json=data, timeout=5,
                                     auth=aiohttp.BasicAuth(USERNAME, PASSWORD)) as response:
                response.raise_for_status()  # HTTPError для ответов с кодами состояния 4xx/5xx
                return True, await response.json()

        except (aiohttp.ClientError, asyncio.TimeoutError) as error:
            print(f'update_transport function error - {error}')
            return False, error  # Возвращаем сообщение об ошибке запроса

        except (ValueError, KeyError) as JSON_error:  # Обработка ошибок парсинга JSON и доступа к ключам
            print(f'update_transport function JSON_error - {JSON_error}')
            return False, {"status": "invalid response"}


async def get_batch_gas(batch_type: str = ''):
    """Проверяет наличие в базе данных активных партий приёмки/отгрузки газа в автоцистернах и возвращает данные
    активной партии, если партия есть в базе, и None - если таких партий нет.

    Args:
        batch_type (str): тип обрабатываемой партии

    Returns:
        dict: данные партии.
    """

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(f"{BASE_URL}/auto-gas", timeout=5,
                                   auth=aiohttp.BasicAuth(USERNAME, PASSWORD)) as response:
                response.raise_for_status()
                batch_data = await response.json()
                return batch_data

        except (aiohttp.ClientError, asyncio.TimeoutError) as error:
            print(f'get_batch_gas function error - {error}')
            return None

        except (ValueError, KeyError) as JSON_error:  # Обработка ошибок парсинга JSON и доступа к ключам
            print(f'get_batch_gas function JSON_error - {JSON_error}')
            return None


async def create_batch_gas(data):
    """Создает новую партию приёмки/отгрузки газа в автоцистернах с использованием асинхронного HTTP-запроса.

    Args:
        data (dict): данные партии газа для создания

    Returns:
        dict: данные созданной партии.
    """

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(f"{BASE_URL}/auto-gas", json=data, timeout=5,
                                    auth=aiohttp.BasicAuth(USERNAME, PASSWORD)) as response:
                response.raise_for_status()
                return await response.json()

        except (aiohttp.ClientError, asyncio.TimeoutError) as error:
            print(f'create_batch_gas function error - {error}')
            return None

        except (ValueError, KeyError) as JSON_error:  # Обработка ошибок парсинга JSON и доступа к ключам
            print(f'create_batch_gas function JSON_error - {JSON_error}')
            return None


async def update_batch_gas(data):
    """
    Обновляет партию приёмки/отгрузки газа в автоцистернах с использованием асинхронного HTTP-запроса.

    Args:
        data (dict): данные партии газа для обновления

    Returns:
        dict: результат обновления.
    """

    async with aiohttp.ClientSession() as session:
        try:
            async with session.patch(f"{BASE_URL}/auto-gas", json=data, timeout=5,
                                     auth=aiohttp.BasicAuth(USERNAME, PASSWORD)) as response:
                response.raise_for_status()  # Поднимает исключение для 4xx и 5xx
                return await response.json()

        except (aiohttp.ClientError, asyncio.TimeoutError) as error:
            print(f'update_batch_gas function error - {error}')
            return None

        except (ValueError, KeyError) as JSON_error:  # Обработка ошибок парсинга JSON и доступа к ключам
            print(f'update_batch_gas function JSON_error - {JSON_error}')
            return None


async def get_railway_batch():
    """Проверяет наличие в базе данных активных партий приёмки газа в жд цистернах и возвращает данные
    активной партии, если партия есть в базе, и None - если таких партий нет.

    Args:

    Returns:
        dict: данные партии.
    """

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(f"{BASE_URL}/railway-loading", timeout=5,
                                   auth=aiohttp.BasicAuth(USERNAME, PASSWORD)) as response:
                response.raise_for_status()
                batch_data = await response.json()
                return batch_data

        except (aiohttp.ClientError, asyncio.TimeoutError) as error:
            print(f'get_railway_batch function error - {error}')
            return None

        except (ValueError, KeyError) as JSON_error:  # Обработка ошибок парсинга JSON и доступа к ключам
            print(f'get_railway_batch function JSON_error - {JSON_error}')
            return None


async def create_railway_batch(data):
    """Создает новую партию приёмки газа в жд цистернах с использованием асинхронного HTTP-запроса.

    Args:
        data (dict): данные для создания партии

    Returns:
        dict: данные созданной партии.
    """

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(f"{BASE_URL}/railway-loading", json=data, timeout=5,
                                    auth=aiohttp.BasicAuth(USERNAME, PASSWORD)) as response:
                response.raise_for_status()
                return await response.json()

        except (aiohttp.ClientError, asyncio.TimeoutError) as error:
            print(f'create_railway_batch function error - {error}')
            return None

        except (ValueError, KeyError) as JSON_error:  # Обработка ошибок парсинга JSON и доступа к ключам
            print(f'create_railway_batch function JSON_error - {JSON_error}')
            return None


async def update_railway_batch(data):
    """
    Обновляет партию приёмки газа в жд цистернах с использованием асинхронного HTTP-запроса.

    Args:
        data (dict): данные для обновления партии

    Returns:
        dict: результат обновления.
    """

    async with aiohttp.ClientSession() as session:
        try:
            async with session.patch(f"{BASE_URL}/railway-loading", json=data, timeout=5,
                                     auth=aiohttp.BasicAuth(USERNAME, PASSWORD)) as response:
                response.raise_for_status()  # Поднимает исключение для 4xx и 5xx
                return await response.json()

        except (aiohttp.ClientError, asyncio.TimeoutError) as error:
            print(f'update_batch_gas function error - {error}')
            return None

        except (ValueError, KeyError) as JSON_error:  # Обработка ошибок парсинга JSON и доступа к ключам
            print(f'update_batch_gas function JSON_error - {JSON_error}')
            return None
