import logging
from celery import shared_task
from railway_service.management.commands.railway_tank import Command as RailwayTankHandleCommand
from railway_service.management.commands.railway_batch import Command as RailwayBatchHandleCommand

logger = logging.getLogger('celery')

@shared_task
def railway_tank_processing():
    command = RailwayTankHandleCommand()
    logger.info('Начало обработки жд цистерн...')
    command.handle()

@shared_task
def railway_batch_processing():
    command = RailwayBatchHandleCommand()
    logger.info('Проверка активных жд партий...')
    command.handle()
