import logging
from celery import shared_task
from transport.management.commands.kpp_processing import Command as KppHandleCommand
from transport.management.commands.kpp_close_transport import Command as CloseTransportHandleCommand

logger = logging.getLogger('kpp')

@shared_task(expires=55)
def kpp_processing():
    command = KppHandleCommand()
    command.handle()

@shared_task(expires=3600)
def kpp_close_transport():
    command = CloseTransportHandleCommand()
    command.handle()
