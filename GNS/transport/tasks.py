import logging
from celery import shared_task
from transport.management.commands.kpp_processing import Command as KppHandleCommand
from transport.management.commands.kpp_close_trasport import Command as CloseTransportHandleCommand

logger = logging.getLogger('kpp')

@shared_task
def kpp_processing():
    command = KppHandleCommand()
    logger.info('Обработка номеров на КПП...')
    command.handle()

@shared_task
def kpp_close_transport():
    command = CloseTransportHandleCommand()
    logger.info('Обновление статусов транспорта...')
    command.handle()
