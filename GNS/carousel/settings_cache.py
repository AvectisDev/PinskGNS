"""
In-memory + Redis кэш настроек карусели.

Hot path постов читает локальный снимок без ORM.
Веб-процесс при save/delete публикует снимок в Redis и бампит revision;
listener подтягивает изменения через sync_from_redis_if_stale().
"""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import asdict, dataclass, fields
from typing import Any, Mapping, Optional

logger = logging.getLogger('carousel')

REDIS_REV_KEY = 'carousel:settings:rev'
REDIS_HASH_KEY = 'carousel:settings:hash'

_lock = threading.RLock()
_store: dict[int, 'CarouselSettingsSnapshot'] = {}
_local_rev: int = 0
_loaded: bool = False


@dataclass(frozen=True)
class CarouselSettingsSnapshot:
    """Снимок полей CarouselSettings, нужных hot path и API настроек."""

    number: int
    name: str = ''
    tcp_host: str = ''
    tcp_port: int = 4001
    rfid_reader_id: Optional[int] = None
    is_active: bool = True
    classify_size_by_weight: bool = False
    size_27_empty_weight_max_g: int = 16000
    read_only: bool = True
    use_weight_management: bool = False
    use_common_correction: bool = False
    weight_correction_value: float = 0.0
    min_balloon_weight_from: float = 15.6
    min_balloon_weight_to: float = 17.8
    max_balloon_weight_from: float = 44.0
    max_balloon_weight_to: float = 46.5
    passport_weight_diff_from: float = 0.0
    passport_weight_diff_to: float = 21.5
    post_1_correction: float = 0.0
    post_2_correction: float = 0.0
    post_3_correction: float = 0.0
    post_4_correction: float = 0.0
    post_5_correction: float = 0.0
    post_6_correction: float = 0.0
    post_7_correction: float = 0.0
    post_8_correction: float = 0.0
    post_9_correction: float = 0.0
    post_10_correction: float = 0.0
    post_11_correction: float = 0.0
    post_12_correction: float = 0.0
    post_13_correction: float = 0.0
    post_14_correction: float = 0.0
    post_15_correction: float = 0.0
    post_16_correction: float = 0.0
    post_17_correction: float = 0.0
    post_18_correction: float = 0.0
    post_19_correction: float = 0.0
    post_20_correction: float = 0.0


_SNAPSHOT_FIELD_NAMES = frozenset(f.name for f in fields(CarouselSettingsSnapshot))


def snapshot_from_model(instance) -> CarouselSettingsSnapshot:
    """Строит снимок из экземпляра CarouselSettings."""
    values = {
        name: getattr(instance, name)
        for name in _SNAPSHOT_FIELD_NAMES
        if name != 'rfid_reader_id'
    }
    values['rfid_reader_id'] = getattr(instance, 'rfid_reader_id', None)
    return CarouselSettingsSnapshot(**values)


def snapshot_to_dict(snapshot: CarouselSettingsSnapshot) -> dict[str, Any]:
    """Словарь, совместимый с бывшим ``Model.values()``."""
    return asdict(snapshot)


def snapshot_from_dict(data: Mapping[str, Any]) -> CarouselSettingsSnapshot:
    """Восстанавливает снимок из dict/JSON."""
    filtered = {
        key: data[key]
        for key in _SNAPSHOT_FIELD_NAMES
        if key in data
    }
    return CarouselSettingsSnapshot(**filtered)


def _get_redis():
    from core.redis_queue import get_redis_client

    return get_redis_client()


def _publish_snapshot(snapshot: CarouselSettingsSnapshot) -> None:
    client = _get_redis()
    client.hset(
        REDIS_HASH_KEY,
        str(snapshot.number),
        json.dumps(snapshot_to_dict(snapshot), ensure_ascii=False),
    )


def _publish_remove(number: int) -> None:
    client = _get_redis()
    client.hdel(REDIS_HASH_KEY, str(number))


def _bump_rev() -> int:
    client = _get_redis()
    return int(client.incr(REDIS_REV_KEY))


def _read_remote_rev() -> Optional[int]:
    try:
        raw = _get_redis().get(REDIS_REV_KEY)
    except Exception as exc:
        logger.warning('Не удалось прочитать revision настроек карусели: %s', exc)
        return None
    if raw is None:
        return 0
    try:
        return int(raw)
    except (TypeError, ValueError):
        return 0


def _replace_store(
    snapshots: dict[int, CarouselSettingsSnapshot],
    rev: int,
) -> None:
    global _store, _local_rev, _loaded
    _store = dict(snapshots)
    _local_rev = rev
    _loaded = True


def reset_cache_for_tests() -> None:
    """Сбрасывает локальный кэш (только для тестов)."""
    global _store, _local_rev, _loaded
    with _lock:
        _store = {}
        _local_rev = 0
        _loaded = False


def load_from_db(*, publish: bool = True) -> dict[int, CarouselSettingsSnapshot]:
    """
    Загружает все CarouselSettings из БД в локальный store.

    Args:
        publish: если True — пишет снимки в Redis и бампит revision.
    """
    from carousel.models import CarouselSettings

    rows = list(CarouselSettings.objects.all().order_by('number'))
    snapshots = {
        row.number: snapshot_from_model(row)
        for row in rows
    }

    with _lock:
        if publish:
            try:
                client = _get_redis()
                pipeline = client.pipeline(transaction=True)
                pipeline.delete(REDIS_HASH_KEY)
                if snapshots:
                    pipeline.hset(
                        REDIS_HASH_KEY,
                        mapping={
                            str(number): json.dumps(
                                snapshot_to_dict(snapshot),
                                ensure_ascii=False,
                            )
                            for number, snapshot in snapshots.items()
                        },
                    )
                pipeline.incr(REDIS_REV_KEY)
                results = pipeline.execute()
                rev = int(results[-1])
            except Exception as exc:
                logger.warning(
                    'Не удалось опубликовать настройки карусели в Redis: %s',
                    exc,
                )
                rev = _local_rev
        else:
            rev = _local_rev

        _replace_store(snapshots, rev)
        return dict(_store)


def load_from_db_and_publish() -> dict[int, CarouselSettingsSnapshot]:
    """Старт listener: ORM → память + Redis."""
    return load_from_db(publish=True)


def ensure_loaded() -> None:
    """Ленивая инициализация кэша из БД (веб/тесты)."""
    with _lock:
        if _loaded:
            return
    load_from_db(publish=True)


def upsert_from_model(instance) -> CarouselSettingsSnapshot:
    """Обновляет локальный кэш и Redis по сохранённой модели."""
    global _local_rev, _loaded
    snapshot = snapshot_from_model(instance)
    with _lock:
        _store[snapshot.number] = snapshot
        _loaded = True
        try:
            _publish_snapshot(snapshot)
            _local_rev = _bump_rev()
        except Exception as exc:
            logger.warning(
                'Не удалось опубликовать снимок карусели %s: %s',
                snapshot.number,
                exc,
            )
        return snapshot


def remove_number(number: int) -> None:
    """Удаляет карусель из локального кэша и Redis."""
    global _local_rev
    with _lock:
        _store.pop(number, None)
        try:
            _publish_remove(number)
            _local_rev = _bump_rev()
        except Exception as exc:
            logger.warning(
                'Не удалось удалить снимок карусели %s из Redis: %s',
                number,
                exc,
            )


def sync_from_redis_if_stale() -> None:
    """
    Если revision в Redis новее локального — перечитывает hash в память.

    При недоступности Redis оставляет текущий снимок (WARNING в лог).
    """
    remote_rev = _read_remote_rev()
    if remote_rev is None:
        return

    with _lock:
        if _loaded and remote_rev == _local_rev:
            return

    try:
        client = _get_redis()
        raw_map = client.hgetall(REDIS_HASH_KEY) or {}
    except Exception as exc:
        logger.warning(
            'Не удалось синхронизировать настройки карусели из Redis: %s',
            exc,
        )
        return

    snapshots: dict[int, CarouselSettingsSnapshot] = {}
    for key, payload in raw_map.items():
        try:
            number = int(key)
            data = json.loads(payload)
            snapshots[number] = snapshot_from_dict(data)
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            logger.warning(
                'Пропуск битого снимка настроек карусели key=%s: %s',
                key,
                exc,
            )

    if not snapshots and remote_rev == 0:
        # Redis пуст — один раз подтянуть из БД
        load_from_db(publish=True)
        return

    with _lock:
        _replace_store(snapshots, remote_rev)


def _orm_fallback(number: int) -> Optional[dict[str, Any]]:
    from carousel.models import CarouselSettings

    row = CarouselSettings.objects.filter(number=number).first()
    if row is None:
        return None
    snapshot = upsert_from_model(row)
    return snapshot_to_dict(snapshot)


def get_settings_dict(number: int) -> Optional[dict[str, Any]]:
    """
    Возвращает dict настроек по бизнес-номеру карусели.

    При miss после sync — один ORM fallback с записью в кэш.
    """
    ensure_loaded()
    sync_from_redis_if_stale()

    with _lock:
        snapshot = _store.get(number)
        if snapshot is not None:
            return snapshot_to_dict(snapshot)

    return _orm_fallback(number)
