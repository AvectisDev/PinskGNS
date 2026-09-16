"""Клиент ocryp: параллельное сравнение номера Интеллекта с OCR."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional, Sequence, Union

import requests
from django.conf import settings

logger = logging.getLogger('railway')
compare_logger = logging.getLogger('railway.ocr_compare')

FORM_FIELD_NAME = 'image'
UPLOAD_FILENAME = 'plate.jpg'
UPLOAD_CONTENT_TYPE = 'image/jpeg'


@dataclass(frozen=True)
class OcrypResult:
    """Результат запроса к ocryp (успех или ошибка без исключения)."""

    number: Optional[str] = None
    candidates: tuple[str, ...] = ()
    elapsed_seconds: Optional[float] = None
    error: Optional[str] = None


def recognize_wagon_number(image_bytes: bytes) -> OcrypResult:
    """Отправляет JPEG в ocryp и возвращает результат без проброса ошибок.

    Args:
        image_bytes: содержимое JPEG-кадра номера.

    Returns:
        OcrypResult с номером/кандидатами либо с полем error.
    """
    url = getattr(settings, 'OCRYP_URL', '') or ''
    if not url:
        return OcrypResult(error='not_configured')

    timeout = float(getattr(settings, 'OCRYP_TIMEOUT', 30))
    files = {
        FORM_FIELD_NAME: (UPLOAD_FILENAME, image_bytes, UPLOAD_CONTENT_TYPE),
    }
    try:
        response = requests.post(url, files=files, timeout=timeout)
    except requests.Timeout:
        return OcrypResult(error='timeout')
    except requests.RequestException as error:
        return OcrypResult(error=f'request_failed:{error.__class__.__name__}')

    if response.status_code != 200:
        return OcrypResult(error=f'http_{response.status_code}')

    try:
        body = response.json()
    except ValueError:
        return OcrypResult(error='invalid_json')

    number = body.get('number')
    raw_candidates = body.get('candidates') or []
    if not isinstance(raw_candidates, list):
        raw_candidates = []
    candidates = tuple(str(item) for item in raw_candidates)
    elapsed = body.get('elapsed_seconds')
    try:
        elapsed_seconds = float(elapsed) if elapsed is not None else None
    except (TypeError, ValueError):
        elapsed_seconds = None

    if number is None:
        return OcrypResult(
            number=None,
            candidates=candidates,
            elapsed_seconds=elapsed_seconds,
            error='null_number',
        )

    return OcrypResult(
        number=str(number),
        candidates=candidates,
        elapsed_seconds=elapsed_seconds,
        error=None,
    )


def log_number_comparison(
    intellect_number: Union[int, str],
    image_bytes: Optional[bytes],
) -> None:
    """Сравнивает номер Интеллекта с OCR и пишет строку в ocr_compare.log.

    Сбой OCR не прерывает обработку весовой. Вызывать только при заданном
    OCRYP_URL (пустой URL = сравнение выключено).
    """
    intellect = str(intellect_number)

    if not image_bytes:
        result = OcrypResult(error='no_photo')
    else:
        result = recognize_wagon_number(image_bytes)

    is_match = bool(result.number) and result.number == intellect
    match_value = 'yes' if is_match else 'no'
    message = _format_compare_line(
        intellect=intellect,
        ocr_number=result.number or '',
        match=match_value,
        candidates=result.candidates,
        elapsed_seconds=result.elapsed_seconds,
        error=result.error,
    )
    compare_logger.info(message)

    if is_match:
        logger.debug('OCR сравнение: %s', message)
    else:
        logger.info('OCR сравнение: %s', message)


def _format_compare_line(
    *,
    intellect: str,
    ocr_number: str,
    match: str,
    candidates: Sequence[str],
    elapsed_seconds: Optional[float],
    error: Optional[str],
) -> str:
    parts = [
        f'intellect={intellect}',
        f'ocr={ocr_number}',
        f'match={match}',
    ]
    if candidates:
        parts.append(f'candidates={",".join(candidates)}')
    if elapsed_seconds is not None:
        parts.append(f'elapsed_s={elapsed_seconds}')
    if error:
        parts.append(f'error={error}')
    return ' '.join(parts)
