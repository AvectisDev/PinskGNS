import logging

from celery import shared_task

from autogas.batch_events import (
    process_autogas_batch_complete as _complete,
    process_autogas_batch_create as _create,
    process_autogas_operator_confirm as _confirm,
)

logger = logging.getLogger('autogas')


@shared_task(expires=60)
def process_autogas_batch_create(payload: dict) -> None:
    """Celery: OPC request_number_identification → propose или список."""
    _create(payload)


@shared_task(expires=60)
def process_autogas_operator_confirm(payload: dict) -> None:
    """Celery: OPC operator_confirm → создание партии."""
    _confirm(payload)


@shared_task(expires=60)
def process_autogas_batch_complete(payload: dict) -> None:
    """Celery: OPC-запрос завершения партии автоколонки."""
    _complete(payload)
