import aiohttp
import requests
import logging


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='balloon_api.log',
    filemode='w',
    encoding='utf-8'
)

logger = logging.getLogger('carousel')
logger.setLevel(logging.DEBUG)


BASE_URL = "http://localhost:8000/api"  # server address
USERNAME = "reader"
PASSWORD = "rfid-device"


async def update_balloon(data):
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(f"{BASE_URL}/balloons/update-by-reader/", json=data, timeout=3,
                                    auth=aiohttp.BasicAuth(USERNAME, PASSWORD)) as response:
                response.raise_for_status()
                return await response.json()

        except Exception as error:
            print(f'update_balloon function error: {error}')
            return data


async def update_balloon_amount(from_who: str, data: dict):
    """Инкрементирует количество баллонов, считанных/определённых rfid-считывателем/оптическим датчиком

    Args:
        from_who (str): От кого пришёл запрос на инкрементирование;
        data (dict): словарь, содержащий значения номера считывателя и соответствующий ему статус.
    """
    if from_who == 'rfid':
        url = f'{BASE_URL}/balloons-amount/update-amount-of-rfid/'
    elif from_who == 'sensor':
        url = f'{BASE_URL}/balloons-amount/update-amount-of-sensor/'
    else:
        return None

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, json=data, timeout=3,
                                    auth=aiohttp.BasicAuth(USERNAME, PASSWORD)) as response:
                response.raise_for_status()

        except Exception as error:
            print(f'update_balloon_amount function error: {error}')
            return None


def put_carousel_data(data: dict, session: requests.Session):
    """
    Функция работает как шлюз между сервером и постом наполнения, т.к. пост может слать запрос только через COM-порт в
    виде набора байт по проприетарному протоколу. Функция отправляет POST-запрос с текущими показаниями поста карусели
    на сервер. В ответ сервер должен прислать требуемый вес газа, которым нужно заправить баллон.
    :param data: Содержит словарь с ключами 'request_type'-тип запроса с поста наполнения, 'post_number' -
    номер поста наполнения, 'weight_combined'- текущий вес баллона, который находится на посту наполнения
    :return: возвращает словарь со статусом ответа и весом баллона
    """
    try:
        logger.debug(f"balloon_api данные поста отправлены - {data}")
        response = session.post(f"{BASE_URL}/carousel/balloon-update/", json=data, timeout=3)
        logger.debug(f"balloon_api данные поста получены - {response}")
        response.raise_for_status()
        if response.content:
            return response.json()
        else:
            return {}

    except requests.exceptions.RequestException as error:
        logger.error(f"put_carousel_data function error: {error}")
        return {}