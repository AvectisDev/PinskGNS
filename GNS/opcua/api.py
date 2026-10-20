"""Синхронный API записи OPC-тегов для Celery workers."""

from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Any, Mapping, Optional

import redis
from django.conf import settings

from opcua.registry import TAGS

logger = logging.getLogger('opcua')

WRITE_QUEUE_KEY = 'opcua:write_queue'
WRITE_POLL_TIMEOUT = 1
WRITE_REPLY_TTL_SECONDS = 30
WRITE_WAIT_TIMEOUT_SECONDS = 8.0
WRITE_WAIT_POLL_SECONDS = 0.05


def _redis_client() -> redis.Redis:
    return redis.Redis.from_url(
        settings.CELERY_BROKER_URL,
        decode_responses=True,
    )


def write_tag(
    name: str,
    value: Any,
    *,
    reply_to: Optional[str] = None,
) -> bool:
    """
    Ставит запрос на запись тега в очередь bridge.

    По умолчанию fire-and-forget. Если передан reply_to — bridge положит
    ACK в этот Redis-ключ после попытки записи.

    Returns:
        True если запрос поставлен в Redis, False при ошибке постановки.
    """
    if name not in TAGS:
        logger.error('OPC write: неизвестный тег %s', name)
        return False

    payload: dict[str, Any] = {
        'id': str(uuid.uuid4()),
        'name': name,
        'value': value,
    }
    if reply_to:
        payload['reply_to'] = reply_to

    try:
        _redis_client().lpush(WRITE_QUEUE_KEY, json.dumps(payload, default=str))
        logger.debug('OPC write enqueued %s=%s', name, value)
    except Exception as error:
        logger.error('OPC write enqueue error для %s: %s', name, error, exc_info=True)
        return False
    return True


def write_tags(values: dict[str, Any]) -> bool:
    """Ставит несколько тегов в очередь. False если любая постановка не удалась."""
    ok = True
    for name, value in values.items():
        if not write_tag(name, value):
            ok = False
    return ok


def publish_write_ack(
    reply_to: str,
    ok: bool,
    error: Optional[str] = None,
) -> None:
    """Публикует результат записи для ожидающего write_tag_wait."""
    payload = json.dumps({'ok': ok, 'error': error})
    try:
        _redis_client().setex(reply_to, WRITE_REPLY_TTL_SECONDS, payload)
    except Exception as exc:
        logger.error('OPC write ACK publish failed %s: %s', reply_to, exc, exc_info=True)


def _wait_write_ack(reply_to: str, timeout: float) -> bool:
    client = _redis_client()
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            raw = client.get(reply_to)
        except Exception as error:
            logger.error('OPC write ACK read error %s: %s', reply_to, error)
            return False
        if raw is not None:
            try:
                client.delete(reply_to)
            except Exception:
                pass
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                return False
            return bool(data.get('ok'))
        time.sleep(WRITE_WAIT_POLL_SECONDS)
    logger.error('OPC write wait timeout (%ss) для %s', timeout, reply_to)
    return False


def write_tag_wait(
    name: str,
    value: Any,
    *,
    timeout: float = WRITE_WAIT_TIMEOUT_SECONDS,
) -> bool:
    """Ставит запись и ждёт ACK от bridge. False при enqueue/timeout/fail."""
    reply_to = f'opcua:write_ack:{uuid.uuid4()}'
    if not write_tag(name, value, reply_to=reply_to):
        return False
    return _wait_write_ack(reply_to, timeout)


def write_tags_wait(
    values: Mapping[str, Any],
    *,
    timeout: float = WRITE_WAIT_TIMEOUT_SECONDS,
) -> bool:
    """
    Пишет теги последовательно с ожиданием ACK каждого.

    False если любой enqueue/запись не удались (оставшиеся не ставятся).
    """
    for name, value in values.items():
        if not write_tag_wait(name, value, timeout=timeout):
            logger.error('OPC write_tags_wait прерван на %s=%r', name, value)
            return False
    return True


def pop_write_request(timeout: int = WRITE_POLL_TIMEOUT) -> Optional[dict[str, Any]]:
    """Читает один write-запрос (для bridge)."""
    client = _redis_client()
    item = client.brpop(WRITE_QUEUE_KEY, timeout=int(timeout))
    if item is None:
        return None
    _, raw = item
    return json.loads(raw)
