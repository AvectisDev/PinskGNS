"""Синхронный API записи OPC-тегов для Celery workers."""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Optional

import redis
from django.conf import settings

from opcua.registry import TAGS

logger = logging.getLogger('opcua')

WRITE_QUEUE_KEY = 'opcua:write_queue'
WRITE_RESULT_PREFIX = 'opcua:write_result:'
DEFAULT_WRITE_TIMEOUT = 5.0


def _redis_client() -> redis.Redis:
    return redis.Redis.from_url(
        settings.CELERY_BROKER_URL,
        decode_responses=True,
    )


def write_tag(
    name: str,
    value: Any,
    *,
    timeout: float = DEFAULT_WRITE_TIMEOUT,
) -> bool:
    """
    Ставит запрос на запись тега в очередь bridge-процесса и ждёт ACK.

    Returns:
        True при успешной записи, False при ошибке/таймауте.
    """
    if name not in TAGS:
        logger.error('OPC write: неизвестный тег %s', name)
        return False

    request_id = str(uuid.uuid4())
    payload = json.dumps({
        'id': request_id,
        'name': name,
        'value': value,
    }, default=str)
    client = _redis_client()
    result_key = f'{WRITE_RESULT_PREFIX}{request_id}'
    try:
        client.lpush(WRITE_QUEUE_KEY, payload)
        result = client.blpop(result_key, timeout=timeout)
        if result is None:
            logger.error('OPC write timeout для %s=%s', name, value)
            return False
        _, status = result
        if status != 'ok':
            logger.error('OPC write failed для %s: %s', name, status)
            return False
        return True
    except Exception as error:
        logger.error('OPC write error для %s: %s', name, error, exc_info=True)
        return False
    finally:
        try:
            client.delete(result_key)
        except Exception:
            pass


def write_tags(values: dict[str, Any], *, timeout: float = DEFAULT_WRITE_TIMEOUT) -> bool:
    """Записывает несколько тегов последовательно. False если любая запись не удалась."""
    ok = True
    for name, value in values.items():
        if not write_tag(name, value, timeout=timeout):
            ok = False
    return ok


def enqueue_write_raw(payload: str) -> None:
    """Низкоуровневая постановка в очередь (для тестов)."""
    _redis_client().lpush(WRITE_QUEUE_KEY, payload)


def pop_write_request(timeout: float = 1.0) -> Optional[dict[str, Any]]:
    """Читает один write-запрос (для bridge)."""
    client = _redis_client()
    item = client.brpop(WRITE_QUEUE_KEY, timeout=timeout)
    if item is None:
        return None
    _, raw = item
    return json.loads(raw)


def publish_write_result(request_id: str, status: str) -> None:
    """Публикует результат записи для ожидающего worker."""
    client = _redis_client()
    key = f'{WRITE_RESULT_PREFIX}{request_id}'
    client.lpush(key, status)
    client.expire(key, 60)
