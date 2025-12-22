import requests
import logging
from datetime import datetime
from typing import Optional
from django.conf import settings


logger = logging.getLogger('filling_station')


def get_current_ttn_from_miriada() -> Optional[list]:
    """
    Получает список текущих ТТН из API Мириады.
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
    или [] в случае ошибки.
    """
    url = f'{settings.MIRIADA_API_URL}/getcurrentttn?realm=brestoblgas'
    headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/json'
    }

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

        # Отправляем запрос в Мириада
        response = session.send(prepared, timeout=2)
        response.raise_for_status()

        result = response.json()
        
        logger.warning(f"Данные по ТТН из Мириады: {type(result)}")

        # Обратботка списка ТТН из Мириады
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
        logger.error(f"Запрос списка ТТН прошёл с ошибкой: {str(e)}")
    except (ValueError, TypeError) as e:
        logger.error(f"Ошибка обработки данных списка ТТН: {str(e)}")
    except Exception as e:
        logger.error(f"Непредвиденная ошибка при получении списка ТТН из Мириады: {str(e)}")

    return []


def close_ttn_in_miriada(ttn_id: int) -> bool:
    """
    Закрывает ТТН в Мириаде по её ID.
    Args:
        ttn_id (int): ID ТТН в системе Мириада
    Returns:
        bool: True при успешном закрытии, False в случае ошибки
    """
    url = f'{settings.MIRIADA_API_POST_URL}/closettn'

    headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/json'
    }

    payload = {
        'id_ttn': ttn_id,
        'realm': 'brestoblgas'
    }

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
            else:
                logger.error(f"ТТН {ttn_id} не закрыта. Ответ: {result}")
                return False
        else:
            logger.error(
                f"Ошибка при закрытии ТТН {ttn_id}! "
                f"Status: {response.status_code} {response.reason}, Ответ: {response.text}")
            return False

    except Exception as error:
        logger.error(f'Ошибка при закрытии ТТН {ttn_id} в Мириаде: {error}')
        return False