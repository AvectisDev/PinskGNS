import requests
import logging
from django.utils import timezone
from typing import Optional, Dict, Any, Union, Tuple
from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ObjectDoesNotExist
from .models import Balloon, Reader, BalloonsBatch, ReaderSettings, Truck, Trailer, DailyReaderCounter, TotalReadersCounter
from .exceptions import (
    ReaderNotFoundError,
    BalloonNotFoundError,
    MiriadaAPIError,
    BatchNotFoundError,
    TransportNotFoundError,
)


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
        reg_number: Регистрационный номер
        
    Returns:
        Кортеж из найденного грузовика и прицепа (может быть None)
    """
    if not reg_number:
        return None, None
        
    normalized_number = normalize_registration_number(reg_number)
    
    try:
        # Пытаемся найти грузовик
        truck = Truck.objects.filter(registration_number=normalized_number).first()
        
        # Пытаемся найти прицеп
        trailer = Trailer.objects.filter(registration_number=normalized_number).first()
        
        return truck, trailer
    except Exception as e:
        logger.error(f"Ошибка при поиске транспорта по номеру {reg_number}: {e}")
        return None, None


def processing_request_without_nfc(reader_number: int) -> None:
    """
    Обрабатывает сигнал от ридера о сработке оптического датчика.
    
    Args:
        reader_number: Номер считывателя
        
    Raises:
        ReaderNotFoundError: Если считыватель не найден
    """
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
            case 3 | 4:
                TotalReadersCounter.sub_full_balloon()

        logger.info(f'Ридер {reader_number}. Создана запись баллона без NFC')
    except ObjectDoesNotExist:
        error_msg = f"Ридер {reader_number} не найден в настройках"
        logger.error(error_msg)
        raise ReaderNotFoundError(error_msg) from None
    except Exception as error:
        logger.error(f"Ошибка обработки сигнала от оптического датчика: {error}")
        raise


def processing_request_with_nfc(nfc_tag: str, reader_number: int) -> Optional[Tuple[Balloon, ReaderSettings]]:
    """
    Обрабатывает сигнал от ридера при получении метки.
    
    Args:
        nfc_tag: NFC метка баллона
        reader_number: Номер считывателя
        
    Returns:
        Кортеж (Balloon, ReaderSettings) при успехе, None в случае ошибки
        
    Raises:
        ReaderNotFoundError: Если считыватель не найден
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
            case 1 | 6:  # временно пока не заменят оптический датчик
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
    except ObjectDoesNotExist:
        error_msg = f"Ридер {reader_number} не найден в настройках"
        logger.error(error_msg)
        raise ReaderNotFoundError(error_msg) from None
    except Exception as error:
        logger.error(f"Ошибка при создании/изменении паспорта баллона: {error}")
        return None


def update_balloon_passport(balloon: Balloon) -> None:
    """
    Обрабатывает данные от API Мириады и обновляет запись баллона.
    
    Args:
        balloon: Объект баллона для обновления
        
    Raises:
        MiriadaAPIError: При ошибках взаимодействия с API
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
    except MiriadaAPIError:
        raise
    except Exception as e:
        logger.error(f"Ошибка при обновлении паспорта баллона {balloon.nfc_tag}: {e}")
        raise


def add_balloon_to_batch(reader: ReaderSettings, balloon: Optional[Balloon] = None) -> Optional[Dict[str, Any]]:
    """
    Добавляет баллон в активную партию в зависимости от номера ридера, к которому привязана партия.
    
    Args:
        reader: Настройки считывателя
        balloon: Объект баллона (опционально)
        
    Returns:
        Словарь с результатом операции или None при ошибке
    """
    if not balloon:
        return None
        
    try:
        batch = BalloonsBatch.objects.select_related('truck', 'trailer', 'truck__type').filter(
            batch_type=reader.function,
            started_at__date=timezone.now().date(),
            reader_number=reader.number,
            is_active=True
        ).first()

        if not batch:
            logger.warning(f'Нет подходящей партии баллонов для ридера {reader.number}')
            return {'message': f'Нет подходящей партии баллонов'}

        result = batch.add_balloon(balloon.nfc_tag)
        if result.get('success', False):
            logger.info(f"Баллон {balloon.nfc_tag} добавлен в партию {batch.id}")
        else:
            logger.warning(f"Не удалось добавить баллон {balloon.nfc_tag} в партию: {result.get('message')}")
            
        return result
    except Exception as e:
        logger.error(f"Ошибка добавления баллона {balloon.nfc_tag if balloon else 'None'} в партию: {e}")
        return None


def add_balloon_to_reader_table(balloon: Balloon, reader: ReaderSettings) -> None:
    """
    Добавляет запись о прохождении баллона с меткой через определённый ридер в таблицу.
    
    Args:
        balloon: Объект баллона
        reader: Настройки считывателя
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
        logger.debug(f"Баллон {balloon.nfc_tag} добавлен в таблицу считывателей для ридера {reader.number}")
    except Exception as error:
        logger.error(f"Ошибка добавления баллона с NFC {balloon.nfc_tag} в таблицу считывателей: {error}")
        raise


def add_balloon_to_cache(balloon: Balloon, reader: ReaderSettings) -> None:
    """
    Добавляет баллон в кеш на считывателе, который находится перед каруселью наполнения баллонов.
    
    Args:
        balloon: Объект баллона
        reader: Настройки считывателя
    """
    CACHE_TIMEOUT_MINUTES = 10
    CACHE_TIMEOUT_SECONDS = CACHE_TIMEOUT_MINUTES * 60
    
    try:
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

        cache.set(cache_key, stack, timeout=CACHE_TIMEOUT_SECONDS)
    except Exception as error:
        logger.error(f"Ошибка добавления баллона с NFC {balloon.nfc_tag} в кеш: {error}")
        raise


def get_balloon_data_from_miriada(nfc_tag: str) -> Optional[Dict[str, Any]]:
    """
    Получает данные баллона по NFC-метке из API Мириады.
    
    Args:
        nfc_tag: NFC метка баллона
        
    Returns:
        Словарь с данными баллона при успешном ответе, None при ошибке
        
    Raises:
        MiriadaAPIError: При критических ошибках взаимодействия с API
    """
    if not nfc_tag:
        logger.warning("Пустая NFC метка при запросе данных из Мириады")
        return None
        
    url = f'{settings.MIRIADA_API_URL}/getballoonbynfctag?nfctag={nfc_tag}&realm=brestoblgas'

    try:
        response = requests.get(url, timeout=2)
        response.raise_for_status()
        result = response.json()

        if result.get('status') != "Ok":
            error_msg = f'Ошибка при получении паспорта баллона. Метка: {nfc_tag}. Ответ: {result}'
            logger.warning(error_msg)
            raise MiriadaAPIError(error_msg)

        balloon_data = result.get('List')
        if not isinstance(balloon_data, dict):
            error_msg = (f"Неправильный формат полученных данных. Метка: {nfc_tag}. "
                        f"Ожидается dict, получено: {type(balloon_data)}")
            logger.error(error_msg)
            raise MiriadaAPIError(error_msg)

        processed_data = {
            'number': balloon_data.get('number'),
            'netto': float(balloon_data.get('netto', 0)),
            'brutto': float(balloon_data.get('brutto', 0)),
            'status': bool(balloon_data.get('status', 0))
        }

        logger.info(f"Данные баллона получены из Мириады: {nfc_tag}")
        return processed_data

    except requests.exceptions.RequestException as e:
        error_msg = f"Запрос баллона с меткой {nfc_tag} прошёл с ошибкой: {str(e)}"
        logger.error(error_msg)
        raise MiriadaAPIError(error_msg) from e
    except (ValueError, TypeError) as e:
        error_msg = f"Ошибка обработки данных. Метка {nfc_tag}: {str(e)}"
        logger.error(error_msg)
        raise MiriadaAPIError(error_msg) from e
    except MiriadaAPIError:
        raise
    except Exception as e:
        error_msg = f"Непредвиденная ошибка при получении данных из Мириады. Метка {nfc_tag}: {str(e)}"
        logger.error(error_msg)
        raise MiriadaAPIError(error_msg) from e


def _format_registration_number(reg_number: str) -> str:
    """
    Форматирует регистрационный номер в формат "AM 7881-2".
    
    Args:
        reg_number: Номер в формате "AM78812"
        
    Returns:
        Отформатированный номер
    """
    if len(reg_number) >= 7:
        return f"{reg_number[:2]} {reg_number[2:6]}-{reg_number[6]}"
    return reg_number


def _get_batch_data_for_loading(reader: int, nfc_tag: str) -> Dict[str, Any]:
    """
    Получает данные партии для отправки статуса загрузки.
    
    Args:
        reader: Номер считывателя
        nfc_tag: NFC метка баллона
        
    Returns:
        Словарь с данными для payload
    """
    data = {'send_type': 'loading_into_truck', 'fulness': 1}
    
    batch = BalloonsBatch.objects.select_related('truck', 'truck__type', 'trailer').filter(
        batch_type='u',
        is_active=True,
        balloon_list__nfc_tag=nfc_tag
    ).first()

    if batch:
        number_auto = batch.truck.registration_number
        data['number_auto'] = _format_registration_number(number_auto)
        data['type_car'] = 0 if batch.truck.type.type == 'Клетевоз' else 1
        if batch.ttn_id:
            data['ttn_id'] = batch.ttn_id
    
    return data


def _get_batch_data_for_unloading(reader: int) -> Dict[str, Any]:
    """
    Получает данные партии для отправки статуса разгрузки.
    
    Args:
        reader: Номер считывателя
        
    Returns:
        Словарь с данными для payload
    """
    data = {'send_type': 'registering_in_warehouse', 'fulness': 0}
    
    batch = BalloonsBatch.objects.select_related('truck', 'trailer').filter(
        batch_type='l',
        is_active=True,
    ).first()
    
    if batch and batch.ttn_id:
        data['ttn_id'] = batch.ttn_id
    
    return data


def _get_send_urls() -> Dict[str, str]:
    """Возвращает словарь URL для отправки статусов в Мириаду."""
    return {
        'filling': f'{settings.MIRIADA_API_POST_URL}/fillingballoon',
        'registering_in_warehouse': f'{settings.MIRIADA_API_POST_URL}/balloontosklad',
        'loading_into_truck': f'{settings.MIRIADA_API_POST_URL}/balloontocar',
    }


def _prepare_payload_for_miriada(reader: int, nfc_tag: str) -> Tuple[str, Dict[str, Any], str]:
    """
    Подготавливает payload для отправки в Мириаду в зависимости от номера считывателя.
    
    Args:
        reader: Номер считывателя
        nfc_tag: NFC метка баллона
        
    Returns:
        Кортеж (url, payload, send_type)
    """
    send_urls = _get_send_urls()
    
    payload = {
        'nfctag': nfc_tag,
        'realm': 'brestoblgas'
    }
    
    if reader == 8:
        send_type = 'filling'
    elif reader == 6:
        batch_data = _get_batch_data_for_unloading(reader)
        send_type = batch_data.pop('send_type')
        payload.update(batch_data)
    elif reader == 5:
        send_type = 'registering_in_warehouse'
        payload['fulness'] = 1
    elif reader in [2, 3, 4]:
        batch_data = _get_batch_data_for_loading(reader, nfc_tag)
        send_type = batch_data.pop('send_type')
        payload.update(batch_data)
    else:
        raise ValueError(f"Неизвестный номер считывателя: {reader}")
    
    url = send_urls.get(send_type)
    if not url:
        raise ValueError(f"Неизвестный тип отправки: {send_type}")
    
    return url, payload, send_type


def send_status_to_miriada(reader: int, nfc_tag: str) -> None:
    """
    Отправляет статусы баллонов по NFC-метке в Мириаду.
    
    Поддерживается 3 основных типа отправки:
    - filling - Наполнение баллона (reader == 8)
    - registering_in_warehouse - Регистрация баллона на склад (reader == 5, 6)
    - loading_into_truck - Погрузка баллона в машину (reader == 2, 3, 4)
    
    Args:
        reader: Номер считывателя
        nfc_tag: NFC метка баллона
        
    Raises:
        MiriadaAPIError: При ошибках отправки
    """
    try:
        url, payload, send_type = _prepare_payload_for_miriada(reader, nfc_tag)
        
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }
        
        session = requests.Session()
        req = requests.Request(
            'POST',
            url,
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
            error_msg = (
                f"Ошибка при отправке {send_type}! "
                f"Status: {response.status_code} {response.reason}, Ответ: {response.json()}"
            )
            logger.error(error_msg)
            raise MiriadaAPIError(error_msg)

    except MiriadaAPIError:
        raise
    except ValueError as e:
        error_msg = f"Ошибка подготовки данных для отправки: {str(e)}"
        logger.error(error_msg)
        raise MiriadaAPIError(error_msg) from e
    except Exception as error:
        error_msg = f'Ошибка при отправке статуса баллона в Мириаду: {error}'
        logger.error(error_msg)
        raise MiriadaAPIError(error_msg) from error
