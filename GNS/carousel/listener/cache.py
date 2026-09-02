"""
Кэш недавних запросов постов.

Контроллер поста может повторить тот же кадр в течение ~2 с;
кэш возвращает сохранённый ответ без повторной обработки Redis/ORM.
"""

import logging
import time
from dataclasses import dataclass

from .config import REQUEST_CACHE_SECONDS

logger = logging.getLogger('carousel')


@dataclass(frozen=True)
class CachedRequest:
    """Сохранённый ответ на запрос поста."""

    expires_at: float
    response_packet: bytes | None


recent_requests: dict[tuple[str, int, int], CachedRequest] = {}


def get_cached_request(
    request_type: str,
    post_number: int,
    weight: int,
) -> tuple[bool, bytes | None]:
    """
    Возвращает сохранённый ответ на повторный запрос контроллера.

    Returns:
        (is_duplicate, response_packet) — response_packet может быть None,
        если при первом запросе ответ не требовался.
    """
    now = time.monotonic()
    expired_keys = [
        key for key, request in recent_requests.items()
        if request.expires_at <= now
    ]
    for key in expired_keys:
        recent_requests.pop(key, None)

    request_key = (request_type, post_number, weight)
    cached_request = recent_requests.get(request_key)
    if cached_request is None:
        return False, None

    logger.debug(f"Повторный запрос {request_key}: используется сохранённый ответ")
    return True, cached_request.response_packet


def cache_request_result(
    request_type: str,
    post_number: int,
    weight: int,
    response_packet: bytes | None,
) -> None:
    """Сохраняет результат обработки запроса на REQUEST_CACHE_SECONDS."""
    request_key = (request_type, post_number, weight)
    recent_requests[request_key] = CachedRequest(
        expires_at=time.monotonic() + REQUEST_CACHE_SECONDS,
        response_packet=response_packet,
    )
