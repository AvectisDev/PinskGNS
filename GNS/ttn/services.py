import requests
import logging
import time
from datetime import datetime
from typing import Optional, TYPE_CHECKING
from django.conf import settings

if TYPE_CHECKING:
    from filling_station.models import BalloonsBatch


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

            logger.debug(
                f"Подготовленный запрос:\n"
                f"URL: {prepared.url}\n"
                f"Headers: {prepared.headers}\n"
                f"Body: {prepared.body}"
            )

            response = session.send(prepared, timeout=2)
            response.raise_for_status()

            result = response.json()

            logger.warning(f"Данные по ТТН из Мириады: {type(result)}")

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


def close_ttn_in_miriada(ttn_id: int, batch: Optional['BalloonsBatch'] = None) -> bool:
    """
    Закрывает ТТН в Мириаде по её ID.
    При неуспешном запросе выполняется до 2 повторных попыток.
    Args:
        ttn_id (int): ID ТТН в системе Мириада
        batch: партия баллонов (для логирования состава на момент закрытия)
    Returns:
        bool: True при успешном закрытии, False в случае ошибки после всех попыток
    """
    _log_batch_balloons_on_ttn_close(ttn_id, batch=batch)

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
                f"Подготовленный запрос на закрытие ТТН:\n"
                f"URL: {prepared.url}\n"
                f"Headers: {prepared.headers}\n"
                f"Body: {prepared.body}"
            )

            response = session.send(prepared, timeout=5)
            if response.status_code == 200:
                result = response.json()
                if result.get('result') == 'ok':
                    logger.info(f"ТТН {ttn_id} успешно закрыта в Мириаде")
                    return True
                logger.error(f"ТТН {ttn_id} не закрыта. Ответ: {result}")
            else:
                logger.error(
                    f"Ошибка при закрытии ТТН {ttn_id}! "
                    f"Status: {response.status_code} {response.reason}, Ответ: {response.text}")
        except Exception as error:
            logger.error(f'Ошибка при закрытии ТТН {ttn_id} в Мириаде: {error}')

        if attempt < settings.MIRIADA_REQUEST_RETRIES:
            logger.warning(
                f"Закрытие ТТН {ttn_id} неуспешно, повтор {attempt + 2}/{settings.MIRIADA_REQUEST_RETRIES + 1}"
            )
            time.sleep(settings.MIRIADA_RETRY_DELAY_SECONDS)

    return False