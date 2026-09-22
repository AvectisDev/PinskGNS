from celery import shared_task

from railway_service.management.commands.railway_batch import Command as RailwayBatchHandleCommand
from railway_service.services.tank_events import process_railway_tank_event as _process_event


@shared_task(expires=60)
def process_railway_tank_event(payload: dict) -> None:
    """Celery: событие камеры ЖД весовой от OPC bridge."""
    _process_event(payload)


@shared_task
def railway_batch_processing():
    command = RailwayBatchHandleCommand()
    command.handle()
