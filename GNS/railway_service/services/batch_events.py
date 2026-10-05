"""Обработка OPC-событий ЖД партий (start/end по railway_batch.active)."""

from __future__ import annotations

import logging
from typing import Any, Mapping

from django.db import transaction
from django.utils import timezone

from railway_service.models import RailwayBatch

logger = logging.getLogger('railway')


def _normalize_batch_type(raw: Any) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return RailwayBatch.BatchType.UNKNOWN
    allowed = {choice.value for choice in RailwayBatch.BatchType}
    if value not in allowed:
        return RailwayBatch.BatchType.UNKNOWN
    return value


def process_railway_batch_started(payload: Mapping[str, Any]) -> None:
    """Фронт railway.active FALSE→TRUE: создать активную партию с batch_type."""
    batch_type = _normalize_batch_type(payload.get('batch_type'))
    with transaction.atomic():
        active = (
            RailwayBatch.objects
            .select_for_update()
            .filter(is_active=True)
            .order_by('-started_at', '-pk')
            .first()
        )
        if active is not None:
            if active.batch_type == RailwayBatch.BatchType.UNKNOWN and batch_type:
                active.batch_type = batch_type
                active.save(update_fields=['batch_type'])
                logger.info(
                    'Активная партия %s: обновлён batch_type=%s',
                    active.pk,
                    batch_type,
                )
            else:
                logger.debug(
                    'Активная партия %s уже есть — повторный start игнорируем',
                    active.pk,
                )
            return

        batch = RailwayBatch.objects.create(
            is_active=True,
            batch_type=batch_type,
        )
        logger.info(
            'Создана ЖД партия %s (batch_type=%s)',
            batch.pk,
            batch_type,
        )


def process_railway_batch_ended(payload: Mapping[str, Any]) -> None:
    """Спад railway.active TRUE→FALSE: закрыть активную партию."""
    with transaction.atomic():
        active = (
            RailwayBatch.objects
            .select_for_update()
            .filter(is_active=True)
            .order_by('-started_at', '-pk')
            .first()
        )
        if active is None:
            logger.debug('Нет активной ЖД партии для закрытия')
            return

        active.is_active = False
        active.completed_at = timezone.now()
        active.save(update_fields=['is_active', 'completed_at'])
        logger.info('Закрыта ЖД партия %s', active.pk)
