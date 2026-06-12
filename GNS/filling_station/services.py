import requests
import logging
import time
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
    При неуспешном запросе выполняется до 2 повторных попыток.

    Args:
        nfc_tag: NFC метка баллона

    Returns:
        Словарь с данными баллона при успешном ответе, None при ошибке

    Raises:
        MiriadaAPIError: При критических ошибках взаимодействия с API после всех попыток
    """
    if not nfc_tag:
        logger.warning("Пустая NFC метка при запросе данных из Мириады")
        return None

    url = f'{settings.MIRIADA_API_URL}/getballoonbynfctag?nfctag={nfc_tag}&realm=brestoblgas'

    for attempt in range(settings.MIRIADA_REQUEST_RETRIES + 1):
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

        except (MiriadaAPIError, requests.exceptions.RequestException, ValueError, TypeError) as e:
            if attempt < settings.MIRIADA_REQUEST_RETRIES:
                logger.warning(
                    f"Запрос к Мириаде (метка {nfc_tag}) неуспешен, повтор {attempt + 2}/{settings.MIRIADA_REQUEST_RETRIES + 1}: {e}"
                )
                time.sleep(settings.MIRIADA_RETRY_DELAY_SECONDS)
            else:
                if isinstance(e, MiriadaAPIError):
                    raise
                error_msg = f"Запрос баллона с меткой {nfc_tag} прошёл с ошибкой после {settings.MIRIADA_REQUEST_RETRIES + 1} попыток: {str(e)}"
                logger.error(error_msg)
                raise MiriadaAPIError(error_msg) from e
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


def _build_loading_payload(batch: BalloonsBatch) -> Dict[str, Any]:
    """Формирует payload /balloontocar из данных партии отгрузки."""
    if not batch.truck:
        raise ValueError(f"У партии {batch.id} отсутствует информация о грузовике")

    number_auto = batch.truck.registration_number
    data = {
        'fulness': 1,
        'number_auto': _format_registration_number(number_auto),
    }

    if batch.truck.type and batch.truck.type.type:
        data['type_car'] = 0 if batch.truck.type.type == 'Клетевоз' else 1
    else:
        raise ValueError(f"У грузовика {number_auto} отсутствует тип транспорта")

    if batch.ttn_id:
        data['id_ttn'] = batch.ttn_id

    return data


def _build_unloading_payload(batch: BalloonsBatch) -> Dict[str, Any]:
    """Формирует payload /balloontosklad из данных партии приёмки."""
    if batch.balloons_type == 'e':
        fulness = 0
    elif batch.balloons_type == 'f':
        fulness = 1
    else:
        raise ValueError(
            f"Неизвестное значение balloons_type '{batch.balloons_type}' в партии {batch.id}"
        )

    data = {'fulness': fulness}
    if batch.ttn_id:
        data['id_ttn'] = batch.ttn_id
    return data


def _get_batch_data_for_loading(
    nfc_tag: str,
    batch: Optional[BalloonsBatch] = None,
    reader: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Получает данные партии для отправки статуса загрузки в /balloontocar.

    Если передана партия — используются её данные. Иначе ищется активная партия
    отгрузки с этим баллоном (с фильтром по номеру считывателя, если указан).
    """
    if batch is None:
        queryset = BalloonsBatch.objects.select_related(
            'truck', 'truck__type', 'trailer'
        ).filter(
            batch_type='u',
            is_active=True,
            balloon_list__nfc_tag=nfc_tag,
        )
        if reader is not None:
            queryset = queryset.filter(reader_number=reader)
        batch = queryset.first()
        if not batch:
            raise ValueError(f"Не найдена активная партия отгрузки для баллона {nfc_tag}")
    elif batch.batch_type != 'u':
        raise ValueError(f"Партия {batch.id} не является партией отгрузки")

    return _build_loading_payload(batch)


def _get_batch_data_for_unloading(
    batch: Optional[BalloonsBatch] = None,
    reader: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Получает данные партии для отправки статуса разгрузки в /balloontosklad.

    Если передана партия — используются её данные. Иначе ищется активная партия
    приёмки (с фильтром по номеру считывателя, если указан).
    """
    if batch is None:
        queryset = BalloonsBatch.objects.select_related('truck', 'trailer').filter(
            batch_type='l',
            is_active=True,
        )
        if reader is not None:
            queryset = queryset.filter(reader_number=reader)
        batch = queryset.first()
        if not batch:
            raise ValueError(f"Не найдена активная партия приёмки для считывателя {reader}")
    elif batch.batch_type != 'l':
        raise ValueError(f"Партия {batch.id} не является партией приёмки")

    return _build_unloading_payload(batch)


def _get_send_urls() -> Dict[str, str]:
    """Возвращает словарь URL для отправки статусов в Мириаду."""
    return {
        'filling': f'{settings.MIRIADA_API_POST_URL}/fillingballoon',
        'registering_in_warehouse': f'{settings.MIRIADA_API_POST_URL}/balloontosklad',
        'loading_into_truck': f'{settings.MIRIADA_API_POST_URL}/balloontocar',
    }


def _prepare_payload_for_miriada(
    reader: int,
    nfc_tag: str,
    batch: Optional[BalloonsBatch] = None,
) -> Tuple[str, Dict[str, Any], str]:
    """
    Подготавливает payload для отправки в Мириаду в зависимости от номера считывателя.
    
    Args:
        reader: Номер считывателя
        nfc_tag: NFC метка баллона
        batch: Партия, к которой привязано событие (если известна)
        
    Returns:
        Кортеж (url, payload, send_type)
        
    Raises:
        ValueError: При ошибках подготовки данных
    """
    send_urls = _get_send_urls()
    
    # Базовый payload с обязательными полями
    payload = {
        'nfctag': nfc_tag,  # Используем nfctag как в API
        'realm': 'brestoblgas'
    }
    
    if reader == 8:
        send_type = 'filling'
    elif reader == 6:
        batch_data = _get_batch_data_for_unloading(batch=batch, reader=reader)
        send_type = 'registering_in_warehouse'
        payload.update(batch_data)
    elif reader in [2, 3, 4]:
        batch_data = _get_batch_data_for_loading(nfc_tag=nfc_tag, batch=batch, reader=reader)
        send_type = 'loading_into_truck'
        payload.update(batch_data)
    else:
        raise ValueError(f"Неизвестный номер считывателя: {reader}")
    
    url = send_urls.get(send_type)
    if not url:
        raise ValueError(f"Неизвестный тип отправки: {send_type}")
    
    return url, payload, send_type


def send_status_to_miriada(
    reader: int,
    nfc_tag: str,
    batch: Optional[BalloonsBatch] = None,
) -> None:
    """
    Отправляет статусы баллонов по NFC-метке в Мириаду.
    При неуспешном запросе выполняется до 2 повторных попыток.

    Поддерживается 3 основных типа отправки:
    - filling - Наполнение баллона (reader == 8)
    - registering_in_warehouse - Регистрация баллона на склад (reader == 5, 6)
    - loading_into_truck - Погрузка баллона в машину (reader == 2, 3, 4)

    Args:
        reader: Номер считывателя
        nfc_tag: NFC метка баллона
        batch: Партия, к которой привязано событие (если известна)

    Raises:
        MiriadaAPIError: При ошибках отправки после всех попыток
    """
    try:
        url, payload, send_type = _prepare_payload_for_miriada(reader, nfc_tag, batch=batch)
    except ValueError as e:
        error_msg = f"Ошибка подготовки данных для отправки: {str(e)}"
        logger.error(error_msg)
        raise MiriadaAPIError(error_msg) from e

    headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/json'
    }

    for attempt in range(settings.MIRIADA_REQUEST_RETRIES + 1):
        try:
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
                return
            error_msg = (
                f"Ошибка при отправке {send_type}! "
                f"Status: {response.status_code} {response.reason}, Ответ: {response.json()}"
            )
            logger.error(error_msg)
            raise MiriadaAPIError(error_msg)
        except MiriadaAPIError:
            if attempt < settings.MIRIADA_REQUEST_RETRIES:
                logger.warning(
                    f"Отправка статуса в Мириаду ({send_type}) неуспешна, "
                    f"повтор {attempt + 2}/{settings.MIRIADA_REQUEST_RETRIES + 1}"
                )
                time.sleep(settings.MIRIADA_RETRY_DELAY_SECONDS)
            else:
                raise
        except requests.exceptions.RequestException as e:
            if attempt < settings.MIRIADA_REQUEST_RETRIES:
                logger.warning(
                    f"Запрос к Мириаде ({send_type}) неуспешен, "
                    f"повтор {attempt + 2}/{settings.MIRIADA_REQUEST_RETRIES + 1}: {e}"
                )
                time.sleep(settings.MIRIADA_RETRY_DELAY_SECONDS)
            else:
                error_msg = f'Ошибка при отправке статуса баллона в Мириаду после {settings.MIRIADA_REQUEST_RETRIES + 1} попыток: {e}'
                logger.error(error_msg)
                raise MiriadaAPIError(error_msg) from e


MIRIADA_BALLOON_STATUS_READERS = frozenset({3, 4, 6, 8})


def add_balloon_to_batch_with_miriada(batch: BalloonsBatch, nfc_tag: str) -> dict:
    """
    Добавляет баллон в партию и отправляет статус в Мириаду — как при проходе
    через стационарный считыватель (feig_protocol, readers 3/4/6/8).
    """
    result = batch.add_balloon(nfc_tag)
    if not result.get('success') or not nfc_tag:
        return result

    reader_number = batch.reader_number
    if reader_number not in MIRIADA_BALLOON_STATUS_READERS:
        return result

    batch = BalloonsBatch.objects.select_related('truck', 'truck__type', 'trailer').get(pk=batch.pk)

    try:
        send_status_to_miriada(reader=reader_number, nfc_tag=nfc_tag, batch=batch)
    except MiriadaAPIError as exc:
        logger.error(
            f"Баллон {nfc_tag} добавлен в партию {batch.id}, "
            f"но отправка статуса в Мириаду (ридер {reader_number}) не удалась: {exc}"
        )
        result['miriada_error'] = str(exc)

    return result


MIRIADA_CLOSE_FAILED_MESSAGE = (
    'Не удалось закрыть ТТН в Мириаде. Партия остаётся активной — '
    'можно добавить баллоны и повторить закрытие.'
)


def attempt_close_balloons_batch(batch: BalloonsBatch) -> Tuple[bool, Optional[str]]:
    """
    Закрывает партию баллонов (устанавливает is_active=False, completed_at).
    Если у партии есть ТТН и тип автомобиля не "Клетевоз", пытается закрыть ТТН в Мириаде.
    В любом случае партия завершается, а флаг miriada_close_failed отражает успех отправки.
    """
    from ttn.services import close_ttn_in_miriada

    # Решаем, нужно ли отправлять запрос в Мириаду
    should_send = bool(batch.ttn_id)
    if should_send:
        # Проверяем тип автомобиля: для "Клетевоз" не отправляем
        if batch.truck and batch.truck.type and batch.truck.type.type == "Клетевоз":
            should_send = False

    success = True
    if should_send:
        if not close_ttn_in_miriada(batch.ttn_id, batch=batch):
            success = False
            logger.warning(
                f"Не удалось закрыть ТТН {batch.ttn_id} в Мириаде при закрытии партии {batch.id}"
            )

    # Всегда завершаем партию
    batch.is_active = False
    batch.completed_at = timezone.now()
    batch.miriada_close_failed = not success   # True, если была ошибка
    batch.save(update_fields=['is_active', 'completed_at', 'miriada_close_failed'])

    if success:
        return True, None
    else:
        return False, MIRIADA_CLOSE_FAILED_MESSAGE


BATCH_CLOSE_SERVER_FIELDS = frozenset({
    'is_active',
    'completed_at',
    'miriada_close_failed',
    'id',
    'batch_type',
    'started_at',
    'ttn_name',
})


def save_and_close_balloons_batch(batch: BalloonsBatch, data=None):
    """
    Сохраняет данные партии и закрывает ТТН в Мириаде. Использует BalloonsBatchSerializer.
    Пустое тело запроса допустимо: берутся текущие данные партии из БД.
    """
    from filling_station.api.serializers import BalloonsBatchSerializer

    payload = {
        key: value
        for key, value in (data or {}).items()
        if key not in BATCH_CLOSE_SERVER_FIELDS
    }

    if payload:
        serializer = BalloonsBatchSerializer(batch, data=payload, partial=True)
        if not serializer.is_valid():
            return False, serializer.errors, None
        serializer.save()
        batch.refresh_from_db()

    success, error_message = attempt_close_balloons_batch(batch)
    batch.refresh_from_db()

    if success:
        return True, None, BalloonsBatchSerializer(batch).data

    return False, {
        'message': error_message or MIRIADA_CLOSE_FAILED_MESSAGE,
        'miriada_close_failed': True,
        'id': batch.id,
    }, None
