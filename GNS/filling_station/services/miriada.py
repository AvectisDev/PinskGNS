import logging
import time
from typing import Optional, Dict, Any, Tuple

import requests
from django.conf import settings

from filling_station.exceptions import MiriadaAPIError
from filling_station.models import BalloonsBatch

logger = logging.getLogger('filling_station')


def get_balloon_data_from_miriada(nfc_tag: str) -> Optional[Dict[str, Any]]:
    """
    Получает данные баллона по NFC-метке из API Мириады.
    При неуспешном запросе выполняется до 2 повторных попыток.
    """
    if not nfc_tag:
        logger.warning("Пустая NFC метка при запросе данных из Мириады")
        return None

    url = f'{settings.MIRIADA_API_URL}/getballoonbynfctag?nfctag={nfc_tag}&realm=brestoblgas'

    for attempt in range(settings.MIRIADA_REQUEST_RETRIES + 1):
        try:
            response = requests.get(url, timeout=settings.MIRIADA_TIMEOUT)
            response.raise_for_status()
            result = response.json()

            if result.get('status') != "Ok":
                error_msg = f'Ошибка при получении паспорта баллона. Метка: {nfc_tag}. Ответ: {result}'
                logger.warning(error_msg)
                raise MiriadaAPIError(error_msg)

            balloon_data = result.get('List')
            if not isinstance(balloon_data, dict):
                error_msg = (
                    f"Неправильный формат полученных данных. Метка: {nfc_tag}. "
                    f"Ожидается dict, получено: {type(balloon_data)}"
                )
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
                    f"Запрос к Мириаде (метка {nfc_tag}) неуспешен, "
                    f"повтор {attempt + 2}/{settings.MIRIADA_REQUEST_RETRIES + 1}: {e}"
                )
                time.sleep(settings.MIRIADA_RETRY_DELAY_SECONDS)
            else:
                if isinstance(e, MiriadaAPIError):
                    raise
                error_msg = (
                    f"Запрос баллона с меткой {nfc_tag} прошёл с ошибкой после "
                    f"{settings.MIRIADA_REQUEST_RETRIES + 1} попыток: {str(e)}"
                )
                logger.error(error_msg)
                raise MiriadaAPIError(error_msg) from e
        except Exception as e:
            error_msg = f"Непредвиденная ошибка при получении данных из Мириады. Метка {nfc_tag}: {str(e)}"
            logger.error(error_msg)
            raise MiriadaAPIError(error_msg) from e


def _format_registration_number(reg_number: str) -> str:
    """Форматирует регистрационный номер в формат "AM 7881-2"."""
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
    """Получает данные партии для отправки статуса загрузки в /balloontocar."""
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
    """Получает данные партии для отправки статуса разгрузки в /balloontosklad."""
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
    """Подготавливает payload для отправки в Мириаду в зависимости от номера считывателя."""
    send_urls = _get_send_urls()

    payload = {
        'nfctag': nfc_tag,
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

            response = session.send(prepared, timeout=settings.MIRIADA_TIMEOUT)
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
                error_msg = (
                    f'Ошибка при отправке статуса баллона в Мириаду после '
                    f'{settings.MIRIADA_REQUEST_RETRIES + 1} попыток: {e}'
                )
                logger.error(error_msg)
                raise MiriadaAPIError(error_msg) from e
