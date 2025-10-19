import logging
import time
from django.core.cache import cache
from django.core.files.base import ContentFile
from opcua import Client, ua
from django.core.exceptions import MultipleObjectsReturned
from django.core.management.base import BaseCommand
from django.conf import settings
from datetime import datetime
from ...models import RailwayBatch, RailwayTank, RailwayTankHistory
from .intellect import get_registration_number_list, INTELLECT_SERVER_LIST, get_plate_image

logger = logging.getLogger('railway')


class Command(BaseCommand):
    OPC_NODE_PATHS = {
        "tank_weight": "ns=4; s=Address Space.PLC_SU1.tank.stable_weight",
        "camera_worked": "ns=4; s=Address Space.PLC_SU1.tank.camera_worked",
        "is_on_station": "ns=4; s=Address Space.PLC_SU1.tank.on_station",
    }


    def __init__(self):
        super().__init__()
        self.client = Client(settings.OPC_SERVER_URL)


    def get_opc_value(self, node_key):
        """Получить значение с OPC UA сервера по ключу."""
        node_path = self.OPC_NODE_PATHS.get(node_key)
        if not node_path:
            logger.error(f"Invalid OPC node key: {node_key}")
            return None
        try:
            return self.client.get_node(node_path).get_value()
        except Exception as error:
            logger.error(f"Error getting OPC value for {node_key}: {error}")
            return None


    def set_opc_value(self, node_key, value):
        """Установить значение на OPC UA сервере."""
        node_path = self.OPC_NODE_PATHS.get(node_key)
        if not node_path:
            logger.error(f"Invalid OPC node key: {node_key}")
            return False
        try:
            node = self.client.get_node(node_path)
            node.set_attribute(ua.AttributeIds.Value, ua.DataValue(value))
            return True
        except Exception as error:
            logger.error(f"Error setting OPC value for {node_key}: {error}")
            return False


    def fetch_railway_tank_data(self):
        """
        Отправляет запрос в Интеллект. В ответ приходит JSON со списком словарей. Каждый словарь - это
        описание одной записи (цистерны)
        """
        logger.debug(f'Выполняется запрос к Интеллекту...')
        railway_tank_list = get_registration_number_list(INTELLECT_SERVER_LIST[0])

        if not railway_tank_list:
            logger.error('ЖД цистерна не определена')
            return None, None

        last_tank = railway_tank_list[-1]
        plate_image = last_tank.get('plate_numbers.id')
        photo_of_number = get_plate_image(plate_image) if plate_image else None
        return int(last_tank['number']), photo_of_number


    def batch_process(self, railway_tank):
        """
        Создаёт партию приёмки жд цистерн (если ещё не создана) и добавляет в неё цистерны.
        """
        try:
            railway_batch, batch_created = RailwayBatch.objects.get_or_create(
                is_active=True,
                defaults={
                    'is_active': True
                }
            )
            railway_batch.railway_tank_list.add(railway_tank)
            logger.info(f'Цистерна {railway_tank.registration_number} добавлена в партию {railway_batch.id}')
        except MultipleObjectsReturned:
            logger.error(f"Найдено более одной активной партии")
        except Exception as error:
            logger.error(f"Ошибка при обработке партии: {error}", exc_info=True)


    def tank_process(self, registration_number, image_data, is_on_station, tank_weight):
        """
        Управляет созданием/обновлением данных цистерн
        """
        try:
            # Проверяем наличие цистерны в базе
            railway_tank, tank_created = RailwayTank.objects.get_or_create(
                registration_number=registration_number,
                defaults={
                        'registration_number': registration_number,
                        'is_on_station': is_on_station,
                    }
                )

            # Для новой цистерны всегда создаём новую историческую запись
            if tank_created:
                if is_on_station:
                    RailwayTankHistory.objects.create(
                        tank=railway_tank,
                        arrival_at=datetime.now(),
                        full_weight=tank_weight,
                        arrival_img=ContentFile(image_data, name=f"{registration_number}_arrival.jpg") if image_data else None,
                    )
                else:
                    RailwayTankHistory.objects.create(
                        tank=railway_tank,
                        departure_at=datetime.now(),
                        empty_weight=tank_weight,
                        departure_img=ContentFile(image_data, name=f"{registration_number}_departure.jpg") if image_data else None,
                    )
                logger.info(f"Создана новая цистерна {registration_number} с исторической записью")
                return railway_tank

            # Указываем состояние цистерны
            railway_tank.is_on_station = is_on_station
            railway_tank.save()

            # Для существующей цистерны создаём новую историческую запись при въезде
            if is_on_station:
                RailwayTankHistory.objects.create(
                    tank=railway_tank,
                    arrival_at=datetime.now(),
                    full_weight=tank_weight,
                    arrival_img=ContentFile(image_data, name=f"{registration_number}_arrival.jpg") if image_data else None,
                )
                logger.info(f"Создана историческая запись для цистерны {registration_number} при въезде")
                return railway_tank

            # Если существующая цистерна выезжает, проверям последнюю историческую запись
            open_hist = railway_tank.tank_history.order_by('-id').first()
            
            if not open_hist:
                # Если истории нет, создаем новую запись на выезд
                RailwayTankHistory.objects.create(
                    tank=railway_tank,
                    departure_at=datetime.now(),
                    empty_weight=tank_weight,
                    departure_img=ContentFile(image_data, name=f"{registration_number}_departure.jpg") if image_data else None,
                )
                logger.warning(f"Создана историческая запись для цистерны {registration_number} при выезде (не было истории)")
                return railway_tank

            # Если последнияя историческая запись закрыта по временным меткам
            if open_hist.arrival_at and open_hist.departure_at:
                # Создаём новую запись на выезд
                RailwayTankHistory.objects.create(
                    tank=railway_tank,
                    departure_at=datetime.now(),
                    empty_weight=tank_weight,
                    departure_img=ContentFile(image_data, name=f"{registration_number}_departure.jpg") if image_data else None,
                )
                logger.warning(f"Создана не полная историческая запись для цистерны {registration_number} при выезде")
                return railway_tank

            # Если запись открыта, то работаем с последней исторической записью
            open_hist.departure_at = datetime.now()
            open_hist.empty_weight = tank_weight
            open_hist.gas_weight = open_hist.full_weight - tank_weight if open_hist.full_weight else None

            # Обрабатываем изображение
            if image_data:
                open_hist.departure_img.save(
                    f"{registration_number}_departure.jpg",
                    ContentFile(image_data),
                    save=False
                )

            open_hist.save()
            logger.info(f"Обновлена историческая запись для цистерны {registration_number} при выезде")
            return railway_tank

        except Exception as error:
            logger.error(f"ЖД. Ошибка при создании/обновлении данных цистерны: {error}", exc_info=True)
            return None


    def handle(self, *args, **kwargs):
        try:
            self.client.connect()

            tank_weight = self.get_opc_value("tank_weight")
            camera_worked = self.get_opc_value("camera_worked")
            is_on_station = self.get_opc_value("is_on_station")

            logger.info(f'tank_weight={tank_weight}, camera_worked={camera_worked}, is_on_station={is_on_station}')

            if not camera_worked:
                return

            logger.info(f'Камера сработала. Вес жд цистерны {tank_weight}')
            self.set_opc_value("camera_worked", False)

            # Приостанавливаем выполнение на 2 секунды, чтобы в интеллекте появилась запись с номером цистерны
            time.sleep(2)

            registration_number, image_data = self.fetch_railway_tank_data()

            # Пропускаем, если номер не определён
            if not registration_number:
                logger.error('ЖД цистерна не определена — пропуск обработки')
                return

            if registration_number == cache.get('last_tank_number', None):
                logger.warning(f'ЖД цистерна с номером {registration_number} уже обрабатывалась — пропуск обработки')
                return

            cache.set('last_tank_number', registration_number)

            # Вызываем метод обработки цистерн
            railway_tank = self.tank_process(registration_number, image_data, is_on_station, tank_weight)

            # Добавляем цистерну в активную партию
            if railway_tank:
                self.batch_process(railway_tank)
                logger.info(f'ЖД весовая. Обработка цистерны № {registration_number} успешно завершена')

        except Exception as error:
            logger.error(f'No connection to OPC server: {error}')
        finally:
            self.client.disconnect()
