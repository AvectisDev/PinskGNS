import logging
from celery import shared_task
from .management.commands.generate_1c_file import Command as Generate1cFileCommand
from .services import sync_current_ttn_from_miriada

logger = logging.getLogger('celery')

@shared_task
def generate_1c_file(ttn_number):
    logger.info(f"Задача формирования файла для 1С по ТТН: {ttn_number}")
    command = Generate1cFileCommand()
    command.handle(ttn_number=ttn_number)


@shared_task
def fetch_current_ttn_from_miriada():
    logger.info("Запуск задачи получения текущих ТТН из Мириады")
    saved_count = sync_current_ttn_from_miriada()
    logger.info(f"Задача получения ТТН завершена, сохранено записей: {saved_count}")
