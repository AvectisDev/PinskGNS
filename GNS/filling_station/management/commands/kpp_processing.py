import logging
from django.core.cache import cache
from django.core.management.base import BaseCommand
from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned
from datetime import datetime
from filling_station.models import Truck, Trailer
from .intellect import get_registration_number_list, INTELLECT_SERVER_LIST, get_transport_type, check_on_station

logger = logging.getLogger('filling_station')


class Command(BaseCommand):
    CACHE_TIMEOUT = 5  # Время хранения номера в кэше в секундах

    def get_transport_data(self):
        """
        Функция отправляет запрос в Интеллект. В ответ приходит JSON ответ со списком словарей. Каждый словарь - это
        описание одной записи (цистерны)
        """
        logger.debug(f'КПП. Выполняется запрос к Интеллекту...')
        transport_list = get_registration_number_list(INTELLECT_SERVER_LIST[2])
        logger.debug(f'КПП. Список номеров: {transport_list}')
        return transport_list

    def transport_process(self, registration_number, is_on_station, current_date, current_time, model):
        """
        Функция обновляет данные по грузовику
        """
        if is_on_station:
            update_data = {
                'is_on_station': True,
                'entry_date': current_date,
                'entry_time': current_time,
                'departure_date': None,
                'departure_time': None
            }
        else:
            update_data = {
                'is_on_station': False,
                'departure_date': current_date,
                'departure_time': current_time
            }
        try:
            model.objects.filter(registration_number=registration_number).update(**update_data)
        except ObjectDoesNotExist:
            logger.error(f"Объект с номером {registration_number} не существует")
        except MultipleObjectsReturned:
            logger.error(f"Найдено более одного объекта с номером {registration_number}")

    def handle(self, *args, **kwargs):
        try:
            logger.info('КПП. Обработка регистрационных номеров')
            current_date, current_time = datetime.now().date(), datetime.now().time()

            registration_number_list = self.get_transport_data()

            for transport in registration_number_list:
                registration_number = transport.get('number')

                cache_key = f"transport_{registration_number}"
                if cache.get(cache_key):
                    logger.debug(f'КПП. Номер {registration_number} уже обрабатывался')
                    continue

                cache.set(cache_key, True, self.CACHE_TIMEOUT)

                is_on_station = check_on_station(transport)
                transport_type = get_transport_type(registration_number)

                if transport_type == 'truck':
                    self.transport_process(registration_number, is_on_station, current_date, current_time, Truck)
                elif transport_type == 'trailer':
                    self.transport_process(registration_number, is_on_station, current_date, current_time, Trailer)

                logger.info(f'КПП. Обработка завершена. {transport_type} № {registration_number}')

        except Exception as error:
            logger.error(f"КПП. Ошибка в основном цикле: {error}", exc_info=True)

