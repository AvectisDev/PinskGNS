"""Повторный опрос Интеллекта и сопоставление протоколов с кэшем взвешиваний."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Optional

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from core.intellect import (
    RAILWAY_CAMERA,
    get_plate_image,
    get_registration_number_list,
)

logger = logging.getLogger('railway')

SEEN_PROTOCOL_IDS_KEY = 'railway_seen_protocol_ids'
PENDING_WEIGHINGS_KEY = 'railway_pending_weighings'
CACHE_TTL_SECONDS = 30 * 60
INTELLECT_TIME_FORMAT = '%d.%m.%Y %H:%M:%S'


@dataclass(frozen=True)
class PendingWeighing:
    """Взвешивание без номера, ожидающее протокол Интеллекта."""

    stable_weight: Any
    on_station: bool
    captured_at: str


@dataclass(frozen=True)
class MatchedTank:
    """Пара номер+фото с OPC-взвешиванием."""

    registration_number: int
    protocol_id: str
    image_data: Optional[bytes]
    weighing: PendingWeighing


def _wait_seconds() -> float:
    return float(getattr(settings, 'INTELLECT_RAILWAY_WAIT_SECONDS', 2))


def _attempts() -> int:
    return max(1, int(getattr(settings, 'INTELLECT_RAILWAY_ATTEMPTS', 3)))


def get_seen_protocol_ids() -> set[str]:
    raw = cache.get(SEEN_PROTOCOL_IDS_KEY) or []
    return {str(item) for item in raw}


def mark_protocols_seen(protocol_ids: list[str]) -> None:
    if not protocol_ids:
        return
    seen = get_seen_protocol_ids()
    seen.update(str(item) for item in protocol_ids)
    cache.set(SEEN_PROTOCOL_IDS_KEY, list(seen), timeout=CACHE_TTL_SECONDS)


def get_pending_weighings() -> list[PendingWeighing]:
    raw = cache.get(PENDING_WEIGHINGS_KEY) or []
    result: list[PendingWeighing] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        result.append(
            PendingWeighing(
                stable_weight=item.get('stable_weight'),
                on_station=bool(item.get('on_station')),
                captured_at=str(item.get('captured_at') or ''),
            )
        )
    return result


def set_pending_weighings(weighings: list[PendingWeighing]) -> None:
    payload = [
        {
            'stable_weight': item.stable_weight,
            'on_station': item.on_station,
            'captured_at': item.captured_at,
        }
        for item in weighings
    ]
    cache.set(PENDING_WEIGHINGS_KEY, payload, timeout=CACHE_TTL_SECONDS)


def append_pending_weighing(
    *,
    stable_weight: Any,
    on_station: bool,
    captured_at: Optional[datetime] = None,
) -> PendingWeighing:
    captured = captured_at or timezone.localtime()
    weighing = PendingWeighing(
        stable_weight=stable_weight,
        on_station=bool(on_station),
        captured_at=captured.isoformat(timespec='seconds'),
    )
    pending = get_pending_weighings()
    pending.append(weighing)
    set_pending_weighings(pending)
    return weighing


def clear_pending_weighings() -> list[PendingWeighing]:
    pending = get_pending_weighings()
    cache.delete(PENDING_WEIGHINGS_KEY)
    return pending


def protocol_timestamp(protocol: dict) -> str:
    """Метка времени протокола Интеллекта (поле date, формат дд.мм.гггг чч:мм:сс)."""
    raw = protocol.get('date') or protocol.get('time') or protocol.get('Time') or ''
    return str(raw)


def protocol_id(protocol: dict) -> Optional[str]:
    plate_id = protocol.get('plate_numbers.id')
    if plate_id is not None and str(plate_id).strip() != '':
        return str(plate_id)
    number = protocol.get('number')
    time_value = protocol_timestamp(protocol)
    if number is None:
        return None
    return f'{number}:{time_value}'


def _parse_protocol_time(protocol: dict) -> Optional[datetime]:
    raw = protocol_timestamp(protocol)
    if not raw:
        return None
    try:
        return datetime.strptime(raw, INTELLECT_TIME_FORMAT)
    except ValueError:
        return None


def sort_protocols_oldest_first(protocols: list[dict]) -> list[dict]:
    """Сортировка: ранние первыми. Без date — порядок списка, последний = самый новый."""
    indexed = list(enumerate(protocols))
    has_any_time = any(_parse_protocol_time(item) is not None for _, item in indexed)
    if not has_any_time:
        return list(protocols)

    def sort_key(pair: tuple[int, dict]) -> tuple:
        index, protocol = pair
        parsed = _parse_protocol_time(protocol)
        if parsed is not None:
            return (0, parsed, index)
        # без date — как позиция в списке (последний новее)
        return (1, datetime.min + timedelta(seconds=index), index)

    return [protocol for _, protocol in sorted(indexed, key=sort_key)]


def filter_new_protocols(
    protocols: list[dict],
    seen_ids: Optional[set[str]] = None,
) -> list[dict]:
    seen = seen_ids if seen_ids is not None else get_seen_protocol_ids()
    new_items: list[dict] = []
    for protocol in protocols:
        pid = protocol_id(protocol)
        if pid is None:
            continue
        if pid in seen:
            continue
        number = protocol.get('number')
        if number is None:
            continue
        try:
            int(number)
        except (TypeError, ValueError):
            continue
        new_items.append(protocol)
    return new_items


def poll_new_protocols() -> list[dict]:
    """
    До N попыток: пауза → запрос списка → выход при появлении нового протокола.
    """
    wait_seconds = _wait_seconds()
    attempts = _attempts()
    seen = get_seen_protocol_ids()
    last_new: list[dict] = []

    for attempt in range(1, attempts + 1):
        if wait_seconds > 0:
            time.sleep(wait_seconds)
        logger.debug(
            'Запрос к Интеллекту (попытка %s/%s)...',
            attempt,
            attempts,
        )
        protocols = get_registration_number_list(RAILWAY_CAMERA) or []
        last_new = filter_new_protocols(protocols, seen)
        if last_new:
            logger.info(
                'Интеллект: новых протоколов %s (попытка %s/%s)',
                len(last_new),
                attempt,
                attempts,
            )
            return sort_protocols_oldest_first(last_new)
        logger.warning(
            'Интеллект: новых протоколов нет (попытка %s/%s)',
            attempt,
            attempts,
        )

    return sort_protocols_oldest_first(last_new)


def match_protocols_to_weighings(
    protocols_oldest_first: list[dict],
    weighings_oldest_first: list[PendingWeighing],
) -> tuple[list[MatchedTank], list[PendingWeighing]]:
    """
    Пары от старых к новым. Лишние протоколы игнорируются,
    лишние взвешивания остаются в очереди.
    """
    pair_count = min(len(protocols_oldest_first), len(weighings_oldest_first))
    matched: list[MatchedTank] = []
    for index in range(pair_count):
        protocol = protocols_oldest_first[index]
        weighing = weighings_oldest_first[index]
        pid = protocol_id(protocol)
        if pid is None:
            continue
        registration_number = int(protocol['number'])
        plate_image = protocol.get('plate_numbers.id')
        image_data = get_plate_image(plate_image) if plate_image else None
        matched.append(
            MatchedTank(
                registration_number=registration_number,
                protocol_id=pid,
                image_data=image_data,
                weighing=weighing,
            )
        )
    remaining = weighings_oldest_first[pair_count:]
    return matched, remaining


def matched_newest_first(matched: list[MatchedTank]) -> list[MatchedTank]:
    """Сначала текущая (последняя по времени), затем отложенные."""
    return list(reversed(matched))
