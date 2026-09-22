"""Диспетчер: фронты условий → Celery.delay."""

from __future__ import annotations

import logging
from typing import Any, Mapping

from celery import current_app
from django.core.cache import cache

from opcua.triggers import TRIGGERS, TriggerDef, build_payload

logger = logging.getLogger('opcua')

IDEMPOTENCY_KEY_PREFIX = 'opcua:trigger:'


class TriggerDispatcher:
    """Сравнивает предыдущий и текущий снимок тегов и ставит Celery-задачи."""

    def __init__(self) -> None:
        self._previous: dict[str, Any] = {}
        self._initialized = False

    @property
    def snapshot(self) -> Mapping[str, Any]:
        return self._previous

    def update_tag(self, name: str, value: Any) -> None:
        """Обновляет одно значение в текущем снимке (без диспетчеризации)."""
        self._previous[name] = value

    def on_snapshot(
        self,
        snapshot: Mapping[str, Any],
        *,
        force_pending: bool = False,
    ) -> list[str]:
        """
        Принимает полный/частичный снимок и запускает сработавшие триггеры.

        Args:
            snapshot: Актуальные значения тегов.
            force_pending: При True (после reconnect) срабатывают уже активные
                pending-условия, даже без фронта.
        """
        merged = dict(self._previous)
        merged.update(snapshot)
        fired: list[str] = []

        for trigger in TRIGGERS:
            if self._maybe_fire(trigger, self._previous, merged, force_pending=force_pending):
                fired.append(trigger.name)

        self._previous = merged
        self._initialized = True
        return fired

    def _maybe_fire(
        self,
        trigger: TriggerDef,
        previous: Mapping[str, Any],
        current: Mapping[str, Any],
        *,
        force_pending: bool,
    ) -> bool:
        now_active = trigger.condition(current)
        if not now_active:
            return False

        if self._initialized:
            if trigger.condition(previous):
                return False
        elif not force_pending:
            return False

        cache_key = f'{IDEMPOTENCY_KEY_PREFIX}{trigger.name}'
        if not cache.add(cache_key, True, timeout=trigger.idempotency_ttl):
            logger.debug('Триггер %s пропущен (idempotency)', trigger.name)
            return False

        payload = build_payload(trigger, current)
        try:
            current_app.send_task(trigger.task, args=(payload,))
            logger.info('Триггер %s → %s payload=%s', trigger.name, trigger.task, payload)
            return True
        except Exception as error:
            cache.delete(cache_key)
            logger.error(
                'Не удалось поставить задачу %s: %s',
                trigger.task,
                error,
                exc_info=True,
            )
            return False
