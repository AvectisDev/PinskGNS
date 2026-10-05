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
WRITE_POLL_TIMEOUT = 1


def _redis_client() -> redis.Redis:
    return redis.Redis.from_url(
        settings.CELERY_BROKER_URL,
        decode_responses=True,
    )


def write_tag(name: str, value: Any) -> bool:
    """
    Ставит запрос на запись тега в очередь bridge (fire-and-forget).

    Worker не ждёт ACK: Redis хранит сообщение до обработки bridge,
    ретраи записи в Melsoft выполняются на стороне bridge.

    Returns:
        True если запрос поставлен в Redis, False при ошибке постановки.
    """
    if name not in TAGS:
        logger.error('OPC write: неизвестный тег %s', name)
        return False

    payload = json.dumps({
        'id': str(uuid.uuid4()),
        'name': name,
        'value': value,
    }, default=str)
    try:
        _redis_client().lpush(WRITE_QUEUE_KEY, payload)
        logger.debug('OPC write enqueued %s=%s', name, value)
        return True
    except Exception as error:
        logger.error('OPC write enqueue error для %s: %s', name, error, exc_info=True)
        return False


def write_tags(values: dict[str, Any]) -> bool:
    """Ставит несколько тегов в очередь. False если любая постановка не удалась."""
    ok = True
    for name, value in values.items():
        if not write_tag(name, value):
            ok = False
    return ok


def pop_write_request(timeout: int = WRITE_POLL_TIMEOUT) -> Optional[dict[str, Any]]:
    """Читает один write-запрос (для bridge)."""
    client = _redis_client()
    item = client.brpop(WRITE_QUEUE_KEY, timeout=int(timeout))
    if item is None:
        return None
    _, raw = item
    return json.loads(raw)
