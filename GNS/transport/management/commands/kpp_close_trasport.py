import logging
from django.core.management.base import BaseCommand
from datetime import datetime
from filling_station.models import Truck, Trailer

logger = logging.getLogger('kpp')


class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        update_data = {
            'is_on_station': False,
            'departure_at': datetime.now()
        }

        try:
            trucks = Truck.objects.filter(is_on_station=True).update(**update_data)
            trailers = Trailer.objects.filter(is_on_station=True).update(**update_data)

            logger.info(f'Изменён статус по следующим номерам: грузовики {trucks}, прицепы {trailers}')
        except Exception as error:
            logger.error(f'Ошибка изменения статусов транспорта: {error}')
            return []
