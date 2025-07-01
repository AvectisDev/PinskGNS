import logging
from celery import shared_task
from .management.commands.generate_1c_file import Command as Generate1cFileCommand

logger = logging.getLogger('celery')

@shared_task
def generate_1c_file(ttn_number):
    logger.info(f"Задача формирования файла для 1С по ТТН: {ttn_number}")
    command = Generate1cFileCommand()
    command.handle(ttn_number=ttn_number)
