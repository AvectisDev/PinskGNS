from celery import shared_task

from railway_service.services.batch_events import (
    process_railway_batch_ended as _batch_ended,
    process_railway_batch_started as _batch_started,
)
from railway_service.services.tank_events import process_railway_tank_event as _process_event


@shared_task(expires=60)
def process_railway_tank_event(payload: dict) -> None:
    """Celery: событие камеры ЖД весовой от OPC bridge."""
    _process_event(payload)


@shared_task(expires=60)
def process_railway_batch_started(payload: dict) -> None:
    """Celery: фронт railway.active — создание партии."""
    _batch_started(payload)


@shared_task(expires=60)
def process_railway_batch_ended(payload: dict) -> None:
    """Celery: спад railway.active — закрытие партии."""
    _batch_ended(payload)
