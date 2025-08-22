import logging
from celery import shared_task
from .management.commands.kpp_processing import Command as KppHandleCommand

logger = logging.getLogger('celery')

@shared_task
def kpp_processing():
    command = KppHandleCommand()
    logger.info('Обработка номеров на КПП...')
    command.handle()
