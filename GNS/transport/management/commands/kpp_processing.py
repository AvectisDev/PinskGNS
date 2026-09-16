import logging
from django.core.management.base import BaseCommand
from .intellect import get_registration_number_list, INTELLECT_SERVER_LIST
from transport.services import log_kpp_numbers_snapshot, process_kpp_events

logger = logging.getLogger('kpp')


class Command(BaseCommand):
    def get_transport_data(self):
        transport_list = get_registration_number_list(INTELLECT_SERVER_LIST[2])
        log_kpp_numbers_snapshot([item.get('number') for item in transport_list])
        return transport_list

    def handle(self, *args, **kwargs):
        try:
            process_kpp_events(self.get_transport_data())
        except Exception as error:
            logger.error(f'КПП. Ошибка в основном цикле: {error}', exc_info=True)
