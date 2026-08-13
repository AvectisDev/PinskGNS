import logging
from django.core.management.base import BaseCommand
from transport.services import close_all_on_station

logger = logging.getLogger('kpp')


class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        try:
            trucks, trailers = close_all_on_station()
            logger.info(
                f'Вечернее закрытие КПП: обновлено {trucks} грузовиков, '
                f'{trailers} прицепов'
            )
        except Exception as error:
            logger.error(f'Ошибка изменения статусов транспорта: {error}', exc_info=True)
