import os
import aiohttp
import requests
import django
import logging
from django.conf import settings


# Инициализация Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'GNS.settings')
django.setup()

# Конфигурация логирования из настроек Django
logging.config.dictConfig(settings.LOGGING)
logger = logging.getLogger('carousel')


USERNAME = "reader"
PASSWORD = "rfid-device"


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
        logger.debug(f"api - данные c поста отправлены - {data}")
        response = session.post(f"{settings.DJANGO_API_HOST}/carousel/balloon-update/", json=data, timeout=2)
        logger.debug(f"api - данные от сервера получены - {response}")
        response.raise_for_status()
        if response.content:
            return response.json()
        else:
            return {}

    except requests.exceptions.RequestException as error:
        logger.error(f"Ошибка в функции отправки данных с поста наполнения на API сервера: {error}")
        return {}
