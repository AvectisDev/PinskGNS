import json
import requests
import logging
import time
from datetime import datetime
from typing import Optional, Tuple, TYPE_CHECKING
from django.conf import settings
from django.db import transaction
from django.db.models import QuerySet
from railway_service.models import RailwayTank

if TYPE_CHECKING:
    from filling_station.models import BalloonsBatch
    from ttn.models import AutoTtn, BalloonTtn, RailwayTtn


logger = logging.getLogger('filling_station')


def get_current_ttn_from_miriada() -> Optional[list]:
    """
    Получает список текущих ТТН из API Мириады.
    При неуспешном запросе выполняется до 2 повторных попыток.
    Возвращает список словарей с данными ТТН:
    [
        {
            'ttn_id': int,
            'name': str,
            'auto': str,
            'date': datetime
        },
        ...
    ]
    или [] в случае ошибки после всех попыток.
    """
    url = f'{settings.MIRIADA_API_URL}/getcurrentttn?realm=brestoblgas'
    headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/json'
    }

    for attempt in range(settings.MIRIADA_REQUEST_RETRIES + 1):
        try:
            session = requests.Session()
            req = requests.Request(
                'GET',
                url,
                auth=(settings.MIRIADA_AUTH_LOGIN, settings.MIRIADA_AUTH_PASSWORD),
                headers=headers,
            )
            prepared = session.prepare_request(req)

            logger.debug(f"Запрос списка ТТН из Мириады: {prepared.url}")

            response = session.send(prepared, timeout=settings.MIRIADA_TIMEOUT)
            response.raise_for_status()

            result = response.json()

            # Обработка списка ТТН из Мириады
            processed_list = []
            for ttn in result:
                try:
                    date_obj = datetime.strptime(ttn.get('date'), "%d.%m.%Y").date()

                    processed_ttn = {
                        'ttn_id': ttn.get('id'),
                        'name': ttn.get('name', ''),
                        'auto': ttn.get('car_plate', ''),
                        'date': date_obj,
                    }

                    processed_list.append(processed_ttn)

                except Exception as e:
                    logger.error(f"Ошибка обработки элемента ТТН: {e}. Данные: {ttn}")
                    continue

            logger.info(f"Получено {len(processed_list)} ТТН из Мириады")
            return processed_list

        except requests.exceptions.RequestException as e:
            if attempt < settings.MIRIADA_REQUEST_RETRIES:
                logger.warning(
                    f"Запрос списка ТТН неуспешен, повтор {attempt + 2}/{settings.MIRIADA_REQUEST_RETRIES + 1}: {e}"
                )
                time.sleep(settings.MIRIADA_RETRY_DELAY_SECONDS)
            else:
                logger.error(f"Запрос списка ТТН прошёл с ошибкой после всех попыток: {str(e)}")
        except (ValueError, TypeError) as e:
            if attempt < settings.MIRIADA_REQUEST_RETRIES:
                logger.warning(
                    f"Ошибка обработки данных списка ТТН, повтор {attempt + 2}/{settings.MIRIADA_REQUEST_RETRIES + 1}: {e}"
                )
                time.sleep(settings.MIRIADA_RETRY_DELAY_SECONDS)
            else:
                logger.error(f"Ошибка обработки данных списка ТТН: {str(e)}")
        except Exception as e:
            if attempt < settings.MIRIADA_REQUEST_RETRIES:
                logger.warning(
                    f"Непредвиденная ошибка при получении списка ТТН, повтор {attempt + 2}/{settings.MIRIADA_REQUEST_RETRIES + 1}: {e}"
                )
                time.sleep(settings.MIRIADA_RETRY_DELAY_SECONDS)
            else:
                logger.error(f"Непредвиденная ошибка при получении списка ТТН из Мириады: {str(e)}")

    return []


def sync_current_ttn_from_miriada() -> int:
    """Получает текущие ТТН из Мириады и сохраняет их в БД."""
    from ttn.models import MiriadaTtn

    api_response = get_current_ttn_from_miriada() or []
    saved_count = 0

    for ttn_data in api_response:
        ttn_id = ttn_data.get('ttn_id')
        if not ttn_id:
            logger.error(f"Отсутствует ID ТТН: {ttn_data}")
            continue

        try:
            MiriadaTtn.objects.update_or_create(
                ttn_id=ttn_id,
                defaults={
                    'name': ttn_data.get('name', ''),
                    'auto': ttn_data.get('auto', ''),
                    'date': ttn_data.get('date'),
                },
            )
            saved_count += 1
        except Exception as e:
            logger.error(f"Ошибка сохранения ТТН ID={ttn_id}: {e}")

    logger.info(f"Синхронизировано {saved_count} ТТН из Мириады")
    return saved_count


def _log_batch_balloons_on_ttn_close(ttn_id: int, batch: Optional['BalloonsBatch'] = None) -> None:
    from filling_station.models import BalloonsBatch

    if batch is None:
        batch = (
            BalloonsBatch.objects.filter(ttn_id=ttn_id, is_active=True)
            .prefetch_related('balloon_list')
            .first()
        )
        if batch is None:
            batch = (
                BalloonsBatch.objects.filter(ttn_id=ttn_id)
                .prefetch_related('balloon_list')
                .order_by('-started_at')
                .first()
            )
    else:
        batch = BalloonsBatch.objects.prefetch_related('balloon_list').get(pk=batch.pk)

    if batch is None:
        logger.info(f"Закрытие ТТН {ttn_id}: партия с этим ttn_id не найдена")
        return

    nfc_tags = list(batch.balloon_list.values_list('nfc_tag', flat=True))
    logger.info(
        f"Закрытие ТТН {ttn_id}, партия №{batch.id}: "
        f"количество баллонов={len(nfc_tags)}, nfc_tag={nfc_tags}"
    )


def _parse_miriada_close_error(response_text: str) -> Optional[str]:
    if not response_text:
        return None
    try:
        data = json.loads(response_text)
    except (json.JSONDecodeError, TypeError):
        return response_text.strip() or None
    if not isinstance(data, dict):
        return response_text.strip() or None
    return data.get('description') or data.get('title') or data.get('message')


TTN_COUNT_MISMATCH_MESSAGE = 'Количество не соответствует указанному в ТТН'


def _is_non_retryable_miriada_close_error(status_code: Optional[int], error_text: Optional[str]) -> bool:
    """
    Ответ Мириады про несовпадение количества с ТТН — валидный отказ, без повторов.
    Клиентские 4xx (кроме 408/429) тоже не ретраим.
    """
    if error_text and TTN_COUNT_MISMATCH_MESSAGE in error_text:
        return True
    if status_code is not None and 400 <= status_code < 500 and status_code not in (408, 429):
        return True
    return False


def _is_miriada_success_response(data: dict) -> bool:
    """Мириада может вернуть Result/result со значением Ok/ok."""
    for key, value in data.items():
        if key.lower() == 'result' and str(value).lower() == 'ok':
            return True
    return False


def close_ttn_in_miriada(
    ttn_id: int,
    batch: Optional['BalloonsBatch'] = None,
) -> Tuple[bool, Optional[str]]:
    """
    Закрывает ТТН в Мириаде по её ID.
    При неуспешном запросе выполняется до 2 повторных попыток.
    Args:
        ttn_id (int): ID ТТН в системе Мириада
        batch: партия баллонов (для логирования состава на момент закрытия)
    Returns:
        tuple[bool, str | None]: успех и текст ошибки из ответа Мириады
    """
    _log_batch_balloons_on_ttn_close(ttn_id, batch=batch)
    last_error: Optional[str] = None

    url = f'{settings.MIRIADA_API_POST_URL}/closettn'

    headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/json'
    }

    payload = {
        'id_ttn': ttn_id,
        'realm': 'brestoblgas'
    }

    for attempt in range(settings.MIRIADA_REQUEST_RETRIES + 1):
        status_code: Optional[int] = None
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

            logger.debug(f"Запрос закрытия ТТН {ttn_id} в Мириаде: {prepared.url}")

            response = session.send(prepared, timeout=settings.MIRIADA_TIMEOUT)
            status_code = response.status_code
            if response.status_code == 200:
                result = response.json()
                if isinstance(result, dict) and _is_miriada_success_response(result):
                    logger.info(f"ТТН {ttn_id} успешно закрыта в Мириаде")
                    return True, None
                last_error = (
                    result.get('description')
                    or result.get('message')
                    or str(result)
                )
                logger.error(f"ТТН {ttn_id} не закрыта. Ответ: {result}")
            else:
                last_error = _parse_miriada_close_error(response.text) or (
                    f"Status: {response.status_code} {response.reason}, "
                    f"Ответ: {response.text}"
                )
                logger.error(
                    f"Ошибка при закрытии ТТН {ttn_id}! "
                    f"Status: {response.status_code} {response.reason}, Ответ: {response.text}")
        except Exception as error:
            last_error = str(error)
            logger.error(f'Ошибка при закрытии ТТН {ttn_id} в Мириаде: {error}')

        if _is_non_retryable_miriada_close_error(status_code, last_error):
            return False, last_error

        if attempt < settings.MIRIADA_REQUEST_RETRIES:
            logger.warning(
                f"Закрытие ТТН {ttn_id} неуспешно, повтор {attempt + 2}/{settings.MIRIADA_REQUEST_RETRIES + 1}"
            )
            time.sleep(settings.MIRIADA_RETRY_DELAY_SECONDS)

    return False, last_error


def enqueue_1c_file(ttn_number: Optional[str]) -> None:
    if not ttn_number:
        return
    from ttn.tasks import generate_1c_file

    number = ttn_number
    transaction.on_commit(lambda: generate_1c_file.delay(number))


def get_latest_tank_history(tank: RailwayTank, railway_ttn_number: str):
    return (
        tank.tank_history
        .filter(railway_ttn=railway_ttn_number)
        .order_by('-arrival_at', '-departure_at')
        .first()
    )


def collect_tanks_for_railway_ttn(
    railway_ttn_number: Optional[str],
) -> Tuple[QuerySet, float, float]:
    if not railway_ttn_number:
        return RailwayTank.objects.none(), 0.0, 0.0

    tanks = RailwayTank.objects.filter(
        tank_history__railway_ttn=railway_ttn_number,
    ).distinct()
    scale_total = 0.0
    ttn_total = 0.0
    for tank in tanks:
        hist = get_latest_tank_history(tank, railway_ttn_number)
        if hist:
            scale_total += float(hist.gas_weight or 0)
            ttn_total += float(hist.netto_weight_ttn or 0)
    return tanks, scale_total, ttn_total


def apply_railway_tank_totals(
    ttn: 'RailwayTtn',
    railway_ttn_number: Optional[str] = None,
) -> QuerySet:
    number = railway_ttn_number if railway_ttn_number is not None else ttn.railway_ttn
    tanks, scale_total, ttn_total = collect_tanks_for_railway_ttn(number)
    ttn.total_gas_amount_by_scales = scale_total
    ttn.total_gas_amount_by_ttn = ttn_total
    return tanks


@transaction.atomic
def save_railway_ttn(
    ttn: 'RailwayTtn',
    railway_ttn_number: Optional[str] = None,
) -> 'RailwayTtn':
    number = railway_ttn_number if railway_ttn_number is not None else ttn.railway_ttn
    ttn.railway_ttn = number
    tanks = apply_railway_tank_totals(ttn, number)
    ttn.save()
    ttn.railway_tank_list.set(tanks)
    enqueue_1c_file(ttn.number)
    return ttn


@transaction.atomic
def save_auto_ttn(ttn: 'AutoTtn') -> 'AutoTtn':
    from autogas.models import AutoGasBatchSettings

    batch = ttn.batch
    if batch:
        batch_settings = AutoGasBatchSettings.objects.first()
        if batch_settings and batch_settings.weight_source == 'f':
            ttn.total_gas_amount = batch.gas_amount
            ttn.source_gas_amount = 'Расходомер'
        else:
            ttn.total_gas_amount = batch.weight_gas_amount
            ttn.source_gas_amount = 'Весы'
        ttn.gas_type = batch.gas_type
    ttn.save()
    enqueue_1c_file(ttn.number)
    return ttn


@transaction.atomic
def save_balloon_ttn(ttn: 'BalloonTtn') -> 'BalloonTtn':
    ttn.save()
    enqueue_1c_file(ttn.number)
    return ttn
