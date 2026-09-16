from celery import shared_task
from railway_service.management.commands.railway_tank import Command as RailwayTankHandleCommand
from railway_service.management.commands.railway_batch import Command as RailwayBatchHandleCommand


@shared_task(expires=60)
def railway_tank_processing():
    command = RailwayTankHandleCommand()
    command.handle()


@shared_task
def railway_batch_processing():
    command = RailwayBatchHandleCommand()
    command.handle()
