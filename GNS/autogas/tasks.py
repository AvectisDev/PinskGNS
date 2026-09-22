import logging

from celery import shared_task

from autogas.batch_events import (
    process_autogas_batch_complete as _complete,
    process_autogas_batch_create as _create,
)

logger = logging.getLogger('autogas')


@shared_task(expires=60)
def process_autogas_batch_create(payload: dict) -> None:
    """Celery: OPC-запрос создания партии автоколонки."""
    _create(payload)


@shared_task(expires=60)
def process_autogas_batch_complete(payload: dict) -> None:
    """Celery: OPC-запрос завершения партии автоколонки."""
    _complete(payload)
