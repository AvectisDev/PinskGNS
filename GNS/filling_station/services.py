import requests
import logging
from django.utils import timezone
from typing import Optional, Dict, Any, Union, Tuple
from django.conf import settings
from django.core.cache import cache
from .models import Balloon, Reader, BalloonsBatch, ReaderSettings, Truck, Trailer, DailyReaderCounter, TotalReadersCounter


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
    Args:
        reg_number (str): Регистрационный номер
    Returns:
        Tuple[Optional[Truck], Optional[Trailer]]: Кортеж из найденного грузовика и прицепа
    """
    normalized_number = normalize_registration_number(reg_number)
    
    truck = None
    trailer = None
    
    try:
        # Пытаемся найти грузовик
        truck = Truck.objects.filter(registration_number=normalized_number).first()
        
        # Пытаемся найти прицеп
        trailer = Trailer.objects.filter(registration_number=normalized_number).first()
        
    except Exception as e:
        logger.error(f"Ошибка при поиске транспорта по номеру {reg_number}: {e}")
    
    return truck, trailer


def processing_request_without_nfc(reader_number: int):
    """Обрабатывает сигнал от ридера о сработке оптического датчика"""
    try:
        reader = ReaderSettings.objects.get(number=reader_number)

        # Подсчёт количества
        DailyReaderCounter.add_sensor(reader)
        # Оптический датчик установлен только на считывателях 3,4,5,6
        match reader.number:
            case 6:
                TotalReadersCounter.add_empty_balloon()
            case 5:
                TotalReadersCounter.add_full_balloon()
                TotalReadersCounter.sub_empty_balloon()
            case [3, 4]:
                TotalReadersCounter.sub_full_balloon()

        logger.info(f'Ридер {reader_number}. Создана запись баллона без NFC')
    except ReaderSettings.DoesNotExist:
        logger.error(f"Ридер {reader_number} не найден в настройках")
    except Exception as error:
        logger.error(f"Ошибка обработки сигнала от оптического датчика: {error}")


def processing_request_with_nfc(nfc_tag: str, reader_number: int) -> Union[Tuple[Balloon, ReaderSettings], None]:
    """
    Обрабатывает сигнал от ридера при получении метки.
    Возвращает кортеж (Balloon, Reader) или None в случае ошибки.
    """
    try:
        reader = ReaderSettings.objects.get(number=reader_number)

        balloon, created = Balloon.objects.update_or_create(
            nfc_tag=nfc_tag,
            defaults={
                'status': reader.status
            }
        )
        logger.info(f"Ридер {reader.number}: Сохранение баллона с меткой {nfc_tag} успешно")

        # Подсчёт количества
        DailyReaderCounter.add_rfid(reader)
        match reader.number:
            case [1, 6]:    #временно пока не заменят оптический датчик
                TotalReadersCounter.add_empty_balloon()
            case 2:
                TotalReadersCounter.sub_full_balloon()

        # Проверяем необходимость обновления данных
        if balloon.update_passport_required or reader.number in [1, 6, 7, 8]:
            update_balloon_passport(balloon)

        # Добавляем баллон в партию при необходимости
        if reader.function in ['l', 'u']:
            add_balloon_to_batch(reader, balloon)

        # Добавляем баллон в таблицу считывателей
        add_balloon_to_reader_table(balloon, reader)

        # Добавляем баллон в кеш
        if reader.need_cache:
            add_balloon_to_cache(balloon, reader)

        return balloon, reader
    except Exception as error:
        logger.error(f"Ошибка при создании/изменении паспорта баллона: {error}")
        return None


def update_balloon_passport(balloon: Balloon):
    """
    Обрабатывает данные от API Мириады и обновляет запись баллона
    """
    try:
        api_data = get_balloon_data_from_miriada(balloon.nfc_tag)
        if api_data:
            balloon.serial_number = api_data['number']
            balloon.netto = api_data['netto']
            balloon.brutto = api_data['brutto']
            balloon.filling_status = api_data['status']
            balloon.update_passport_required = False
            balloon.save()
            logger.info(f"Обновление паспорта баллона с меткой {balloon.nfc_tag} успешно")
    except Exception as e:
        logger.error(f"Ошибка при обновлении паспорта баллона {balloon.nfc_tag}: {e}")


def add_balloon_to_batch(reader: ReaderSettings, balloon: Balloon = None):
    """
    Добавляет баллон в активную партию в зависимости от номера ридера, к которому привязана партия.
    """
    try:
        batch = BalloonsBatch.objects.filter(
            batch_type=reader.function,
            started_at__date=timezone.now().today(),
            reader_number=reader.number,
            is_active=True
        ).first()

        if not batch:
            return {'message': f'Нет подходящей партии баллонов'}

        result = batch.add_balloon(balloon.nfc_tag if balloon else None)
        if result.get('success', False):
            logger.info(f"Баллон {balloon.nfc_tag} добавлен в партию {batch.id}")

    except Exception as e:
        logger.error(f"Ошибка добавления баллона {balloon.nfc_tag} в партию: {e}")


def add_balloon_to_reader_table(balloon: Balloon, reader: ReaderSettings):
    """
    Добавляет запись о прохождении баллона с меткой через определённый ридер в таблицу.
    """
    try:
        Reader.objects.create(
            number=reader,
            nfc_tag=balloon.nfc_tag,
            serial_number=balloon.serial_number,
            size=balloon.size,
            netto=balloon.netto,
            brutto=balloon.brutto,
            filling_status=balloon.filling_status
        )
    except Exception as error:
        logger.error(f"Ошибка добавления баллона с NFC {balloon.nfc_tag} в таблицу считывателей: {error}")


def add_balloon_to_cache(balloon: Balloon, reader: ReaderSettings):
    """
    Добавляет баллон в кеш на считывателе, который находится перед каруселью наполнения баллонов.
    """
    try:
        timeout_minutes = 10
        timeout_seconds = timeout_minutes * 60

        cache_key = f'reader_{reader.number}_balloon_stack'
        stack = cache.get(cache_key, [])
        # Добавляем объект в стек
        stack.insert(0, {
            'nfc_tag': balloon.nfc_tag,
            'serial_number': balloon.serial_number,
            'size': balloon.size,
            'netto': balloon.netto,
            'brutto': balloon.brutto,
            'filling_status': balloon.filling_status,
        })
        logger.debug(f'Баллон с NFC {balloon.nfc_tag} добавлен в кеш. Стек: {stack}')

        cache.set(cache_key, stack, timeout=timeout_seconds)
    except Exception as error:
        logger.error(f"Ошибка добавления баллона с NFC {balloon.nfc_tag} в кеш: {error}")


def get_balloon_data_from_miriada(nfc_tag: str) -> Optional[Dict[str, Any]]:
    """
    Получает данные баллона по NFC-метке из API Мириады.
    Возвращает:
        - Dict: данные баллона при успешном ответе
        - None: при ошибке соединения или неверном формате данных
    """
    url = f'{settings.MIRIADA_API_URL}/getballoonbynfctag?nfctag={nfc_tag}&realm=brestoblgas'

    try:
        response = requests.get(url, timeout=2)
        response.raise_for_status()
        result = response.json()

        if result.get('status') != "Ok":
            logger.warning(f'Ошибка при получении паспорта баллона. Метка: {nfc_tag}. Ответ: {result}')
            return None

        balloon_data = result.get('List')
        if not isinstance(balloon_data, dict):
            logger.error(f"Неправильный формат полученных данных. Метка: {nfc_tag}. "
                         f"Ожидается dict, получено: {type(balloon_data)}")
            return None

        processed_data = {
            'number': balloon_data.get('number'),
            'netto': float(balloon_data.get('netto', 0)),
            'brutto': float(balloon_data.get('brutto', 0)),
            'status': bool(balloon_data.get('status', 0))
        }

        logger.info(f"Данные баллона получены из Мириады: {nfc_tag}")
        return processed_data

    except requests.exceptions.RequestException as e:
        logger.error(f"Запрос баллона с меткой {nfc_tag} прошёл с ошибкой: {str(e)}")
    except (ValueError, TypeError) as e:
        logger.error(f"Ошибка обработки данных. Метка {nfc_tag}: {str(e)}")
    except Exception as e:
        logger.error(f"Непредвиденная ошибка при получении данных из Мириады. Метка {nfc_tag}: {str(e)}")

    return None


def send_status_to_miriada(reader: int, nfc_tag: str):
    """
    Метод для отправки статусов баллонов по NFC-метке в Мириаду.
    Поддерживается 3 основных типа отправки (send_type):
    filling - Наполнение баллона
    registering_in_warehouse - Регистрация баллона на склад
    loading_into_truck - Погрузка баллона в машину
    number_auto - номер машины в формате "AM 7881-2". Номер должен быть в ПК «Автопарк»
    type_car - тип машины: 0-кассета, 1 — трал
    ttn_id - ID ТТН в системе Мириада
    """
    send_urls = {
        'filling': f'{settings.MIRIADA_API_POST_URL}/fillingballoon',
        'registering_in_warehouse': f'{settings.MIRIADA_API_POST_URL}/balloontosklad',
        'loading_into_truck': f'{settings.MIRIADA_API_POST_URL}/balloontocar',
    }

    headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/json'
    }

    payload = {
        'nfctag': nfc_tag,
        'realm': 'brestoblgas'
    }

    # Инициализация переменных
    send_type = fullness = number_auto = type_car = ttn_id = None

    if reader == 8:
        send_type = 'filling'
    elif reader == 6:
        send_type = 'registering_in_warehouse'
        fullness = 0
        # Ищем активную партию приёмки, которая содержит этот баллон
        batch = BalloonsBatch.objects.filter(
            batch_type='l',
            is_active=True,
        ).first()
        if batch and batch.ttn_id:
            ttn_id = batch.ttn_id
    elif reader == 5:
        send_type = 'registering_in_warehouse'
        fullness = 1
    elif reader in [2, 3, 4]:
        send_type = 'loading_into_truck'
        fullness = 1
        # Ищем активную партию отгрузки, которая содержит этот баллон
        batch = BalloonsBatch.objects.filter(
            batch_type='u',
            is_active=True,
            balloon_list__nfc_tag=nfc_tag
        ).first()

        if batch:
            number_auto = batch.truck.registration_number
            formatted_number_auto = f"{number_auto[:2]} {number_auto[2:6]}-{number_auto[6]}"
            type_car = 0 if batch.truck.type.type == 'Клетевоз' else 1
            if batch.ttn_id:
                ttn_id = batch.ttn_id

    if fullness is not None:
        payload.update({"fulness": fullness})

    if number_auto is not None and type_car is not None:
        payload.update({
            "number_auto": formatted_number_auto,
            "type_car": type_car
        })
    
    if ttn_id is not None:
        payload.update({"id_ttn": ttn_id})

    try:
        session = requests.Session()
        req = requests.Request(
            'POST',
            send_urls.get(send_type),
            auth=(settings.MIRIADA_AUTH_LOGIN, settings.MIRIADA_AUTH_PASSWORD),
            headers=headers,
            json=payload
        )
        prepared = session.prepare_request(req)

        logger.debug(
            f"Подготовленный запрос:\n"
            f"URL: {prepared.url}\n"
            f"Headers: {prepared.headers}\n"
            f"Body: {prepared.body}"
        )

        response = session.send(prepared, timeout=2)
        if response.status_code == 200:
            logger.info(f"Статус по {send_type} успешно отправлен")
        else:
            logger.error(
                f"Ошибка при отправке {send_type}! "
                f"Status: {response.status_code} {response.reason}, Ответ: {response.json()}")

    except Exception as error:
        logger.error(f'Ошибка при отправке {send_type} в методе отправки статуса баллона в Мириаду: '
                     f'{error}, URL: {prepared.url}')
