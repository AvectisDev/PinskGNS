from __future__ import annotations

import json
from functools import lru_cache
from typing import Any, Mapping, Optional

import redis
from django.conf import settings


@lru_cache(maxsize=1)
def get_redis_client() -> redis.Redis:
    """Возвращает общий клиент Redis из настроек Django cache."""
    location = settings.CACHES['default']['LOCATION']
    if isinstance(location, (list, tuple)):
        location = location[0]
    return redis.Redis.from_url(location, decode_responses=True)


def get_reader_balloon_queue_key(reader_number: int) -> str:
    return f'reader_{reader_number}_balloon_queue'


def push_json_to_queue(
    queue_key: str,
    data: Mapping[str, Any],
    timeout: int,
) -> int:
    """Атомарно добавляет JSON в начало Redis-очереди и обновляет TTL."""
    payload = json.dumps(dict(data), ensure_ascii=False)
    pipeline = get_redis_client().pipeline(transaction=True)
    pipeline.lpush(queue_key, payload)
    pipeline.expire(queue_key, timeout)
    result = pipeline.execute()
    return int(result[0])


def pop_json_from_queue(
    queue_key: str,
) -> tuple[Optional[dict[str, Any]], int]:
    """Извлекает старейший элемент и возвращает размер очереди за один запрос."""
    pipeline = get_redis_client().pipeline(transaction=True)
    pipeline.rpop(queue_key)
    pipeline.llen(queue_key)
    payload, queue_length = pipeline.execute()
    if payload is None:
        return None, int(queue_length)

    data = json.loads(payload)
    if not isinstance(data, dict):
        raise ValueError(f'Элемент Redis-очереди {queue_key} не является объектом')
    return data, int(queue_length)


def get_queue_length(queue_key: str) -> int:
    return int(get_redis_client().llen(queue_key))


def increment_metric(carousel_number: int, metric_name: str) -> int:
    key = f'carousel_{carousel_number}_metric_{metric_name}'
    return int(get_redis_client().incr(key))
