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
        Функция отправляет запрос в Интеллект. В ответ приходит JSON со списком словарей. Каждый словарь - это
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
        Функция создаёт партию приёмки жд цистерн (если ещё не создана) и добавляет в неё цистерны.
        """
        # Проверяем активные партии. Если партии нет - создаём её
        try:
            railway_batch, batch_created = RailwayBatch.objects.get_or_create(
                is_active=True,
                defaults={
                    'is_active': True
                }
            )
            railway_batch.railway_tank_list.add(railway_tank)
        except MultipleObjectsReturned:
            logger.error(f"Найдено более одной активной партии")
        except Exception as error:
            logger.error(f"Ошибка при обработке партии: {error}", exc_info=True)

    def handle(self, *args, **kwargs):
        try:
            self.client.connect()

            tank_weight = self.get_opc_value("tank_weight")
            camera_worked = self.get_opc_value("camera_worked")
            is_on_station = self.get_opc_value("is_on_station")

            logger.debug(f'tank_weight={tank_weight}, camera_worked={camera_worked}, is_on_station={is_on_station}')

            if not camera_worked:
                return

            logger.debug(f'Камера сработала. Вес жд цистерны {tank_weight}')
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

            try:
                # Получаем или создаём цистерну по уникальному номеру
                railway_tank, tank_created = RailwayTank.objects.update_or_create(
                    registration_number=registration_number,
                    defaults={
                        'is_on_station': is_on_station,
                    }
                )

                # 2) Сохраняем/обновляем фото номера (только если получили данные)
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

                # 3) Управляем историей посещений RailwayTankHistory
                if is_on_station:
                    # Открываем или обновляем текущую запись истории, если предыдущая закрыта
                    open_hist = railway_tank.tank_history.filter(departure_at__isnull=True).order_by('-arrival_at').first()
                    if open_hist is None:
                        RailwayTankHistory.objects.create(
                            tank=railway_tank,
                            arrival_at=datetime.now(),
                            full_weight=tank_weight,
                        )
                    else:
                        if open_hist.full_weight is None and tank_weight is not None:
                            open_hist.full_weight = tank_weight
                            open_hist.save()
                else:
                    # Закрываем последнюю незакрытую запись истории
                    open_hist = railway_tank.tank_history.filter(departure_at__isnull=True).order_by('-arrival_at').first()
                    if open_hist is not None:
                        open_hist.departure_at = datetime.now()
                        open_hist.empty_weight = tank_weight
                        if open_hist.full_weight is not None and tank_weight is not None:
                            open_hist.gas_weight = open_hist.full_weight - tank_weight
                        open_hist.save()

                # 4) Добавляем цистерну в активную партию
                self.batch_process(railway_tank)
                logger.debug(f'ЖД весовая. Обработка завершена. Цистерна № {registration_number}')

            except Exception as error:
                logger.error(f"ЖД. Ошибка в основном цикле: {error}", exc_info=True)

        except Exception as error:
            logger.error(f'No connection to OPC server: {error}')
        finally:
            self.client.disconnect()
