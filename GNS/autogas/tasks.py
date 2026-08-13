import logging
from celery import shared_task
from .management.commands.auto_gas_batch import Command as AutoGasBatchHandleCommand

logger = logging.getLogger('autogas')

@shared_task(expires=9)
def auto_gas_processing():
    command = AutoGasBatchHandleCommand()
    command.handle()
