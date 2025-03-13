import logging
import time
from django.core.cache import cache
from django.core.files.base import ContentFile
from opcua import Client, ua
from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned
from django.core.management.base import BaseCommand
from datetime import datetime
from filling_station.models import RailwayBatch, RailwayTank
from .intellect import get_registration_number_list, INTELLECT_SERVER_LIST, get_plate_image

logger = logging.getLogger('filling_station')


class Command(BaseCommand):
    def get_railway_tank_data(self):
        """
        Функция отправляет запрос в Интеллект. В ответ приходит JSON ответ со списком словарей. Каждый словарь - это
        описание одной записи (цистерны)
        """
        logger.debug(f'Выполняется запрос к Интеллекту...')
        railway_tank_list = get_registration_number_list(INTELLECT_SERVER_LIST[0])

        if not railway_tank_list:
            # Если цистерна не определена, то создаём цистерну без номера
            logger.info('ЖД цистерна не определена')
            number = 'Не определён'
            photo_of_number = None
        else:
            # работаем с номером последней цистерны
            railway_tank = railway_tank_list[-1]
            number = railway_tank['number']
            plate_image = railway_tank['plate_numbers.id']
            # Получаем изображение номера
            photo_of_number = get_plate_image(plate_image)
        return number, photo_of_number

    def handle(self, *args, **kwargs):
        try:
            logger.info('Обработка номеров на КПП')

            registration_number, image_data = self.get_railway_tank_data()

            if registration_number != self.last_number:
                cache.set('last_tank_number', self.last_number)

                # Инициализация переменной railway_tank
                railway_tank = None
                try:
                    railway_tank, tank_created = RailwayTank.objects.get_or_create(
                        registration_number=registration_number if registration_number != 'Не определён' else ' ',
                        defaults={
                            'registration_number': registration_number,
                            'is_on_station': is_on_station,
                            'entry_date': current_date if is_on_station else None,
                            'entry_time': current_time if is_on_station else None,
                            'departure_date': current_date if not is_on_station else None,
                            'departure_time': current_time if not is_on_station else None,
                            'full_weight': tank_weight if is_on_station else None,
                            'empty_weight': tank_weight if not is_on_station else None,
                        }
                    )
                    if image_data:
                        image_name = f"{registration_number}.jpg"
                        railway_tank.registration_number_img.save(
                            image_name,
                            ContentFile(image_data),
                            save=True
                        )
                        logger.debug(f'Изображение для цистерны {registration_number} успешно сохранено.')
                    else:
                        logger.error(f'Не удалось получить изображение для цистерны {registration_number}.')

                    if not tank_created:
                        railway_tank.is_on_station = is_on_station
                        if is_on_station:
                            railway_tank.entry_date = current_date
                            railway_tank.entry_time = current_time
                            railway_tank.departure_date = None
                            railway_tank.departure_time = None
                            railway_tank.full_weight = tank_weight
                        else:
                            railway_tank.departure_date = current_date
                            railway_tank.departure_time = current_time
                            railway_tank.empty_weight = tank_weight
                            if railway_tank.full_weight is not None:
                                railway_tank.gas_weight = railway_tank.full_weight - tank_weight
                        railway_tank.save()

                    logger.info(f'ЖД весовая. Обработка завершена. Цистерна № {registration_number}')

                except ObjectDoesNotExist:
                    logger.error(f"Объект с номером {registration_number} не существует")
                except MultipleObjectsReturned:
                    logger.error(f"Найдено более одного объекта с номером {registration_number}")



        except Exception as error:
            logger.error(f'No connection to OPC server: {error}')
        finally:
            self.client.disconnect()
            logger.info('Disconnect from OPC server')
