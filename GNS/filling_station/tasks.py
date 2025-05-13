import logging
from celery import shared_task
from .management.commands.generate_1c_file import Command as Generate1cFileCommand
from .management.commands.auto_gas_batch import Command as AutoGasBatchHandleCommand
from .management.commands.kpp_processing import Command as KppHandleCommand

logger = logging.getLogger('celery')

@shared_task
def generate_1c_file():
    command = Generate1cFileCommand()
    command.handle()

@shared_task
def auto_gas_processing():
    command = AutoGasBatchHandleCommand()
    logger.info('Начало обработки автоцистерн...')
    command.handle()

@shared_task
def kpp_processing():
    command = KppHandleCommand()
    logger.info('Обработка номеров на КПП...')
    command.handle()
