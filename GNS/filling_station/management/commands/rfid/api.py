import os
import django
import aiohttp
import logging.config
from django.conf import settings

# Инициализация Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'GNS.settings')
django.setup()

# Конфигурация логирования из настроек Django
logging.config.dictConfig(django.conf.settings.LOGGING)
logger = logging.getLogger('rfid')

USERNAME = "reader"
PASSWORD = "rfid-device"


async def update_balloon(data):
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(f"{settings.DJANGO_API_HOST}/balloons/update-by-reader/", json=data, timeout=2,
                                    auth=aiohttp.BasicAuth(USERNAME, PASSWORD)) as response:
                response.raise_for_status()
                return await response.json()

        except Exception as error:
            logger.error(f'update_balloon function error: {error}, send_data: {data}, Ответ: {response.json()}')
            return data


async def update_balloon_amount(from_who: str, data: dict):
    """Инкрементирует количество баллонов, считанных/определённых rfid-считывателем/оптическим датчиком

    Args:
        from_who (str): От кого пришёл запрос на инкрементирование;
        data (dict): словарь, содержащий значения номера считывателя и соответствующий ему статус.
    """
    if from_who == 'rfid':
        url = f'{settings.DJANGO_API_HOST}/balloons-amount/update-amount-of-rfid/'
    elif from_who == 'sensor':
        url = f'{settings.DJANGO_API_HOST}/balloons-amount/update-amount-of-sensor/'
    else:
        return None

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                    url,
                    json=data,
                    timeout=2,
                    auth=aiohttp.BasicAuth(USERNAME, PASSWORD)) as response:
                response.raise_for_status()

        except Exception as error:
            logger.error(f'update_balloon_amount function error: {error}, send_data: {data}, Ответ: {response.json()}')
            return None
