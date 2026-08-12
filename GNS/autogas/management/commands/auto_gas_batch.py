import logging
from opcua import ua
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Q
from django.core.cache import cache
from datetime import datetime
from core.opc import create_opc_client, disconnect_opc
from filling_station.models import Truck, Trailer, TrailerType
from autogas.models import AutoGasBatch
from .intellect import get_registration_number_list, INTELLECT_SERVER_LIST


logger = logging.getLogger('autogas')


class Command(BaseCommand):
    DEFAULT_CACHE_TIMEOUT = 1200
    PENDING_REQUEST_CACHE_TIMEOUT = 30

    OPC_NODE_PATHS = {
        "batch_type_code": "ns=4; s=Address Space.PLC_SU2.batch.batch_type", # 1-приёмка, 2-отгрузка
        "gas_type": "ns=4; s=Address Space.PLC_SU2.batch.gas_type", # 1-Не выбран, 2-СПБТ, 3-ПБА
        "stop_batch": "ns=4; s=Address Space.PLC_SU2.batch.stop_batch",
        "initial_mass_meter": "ns=4; s=Address Space.PLC_SU2.batch.initial_mass_meter",
        "final_mass_meter": "ns=4; s=Address Space.PLC_SU2.batch.final_mass_meter",
        "gas_amount": "ns=4; s=Address Space.PLC_SU2.batch.gas_amount",
        "truck_full_weight": "ns=4; s=Address Space.PLC_SU2.batch.truck_full_weight",
        "truck_empty_weight": "ns=4; s=Address Space.PLC_SU2.batch.truck_empty_weight",
        "weight_gas_amount": "ns=4; s=Address Space.PLC_SU2.batch.weight_gas_amount",
        "truck_capacity": "ns=4; s=Address Space.PLC_SU2.batch.truck_capacity",
        "request_batch_create": "ns=4; s=Address Space.PLC_SU2.batch.request_number_identification",
        "response_batch_create": "ns=4; s=Address Space.PLC_SU2.batch.response_number_detect",
        "request_batch_complete": "ns=4; s=Address Space.PLC_SU2.batch.request_batch_complete",
        "response_batch_complete": "ns=4; s=Address Space.PLC_SU2.batch.response_batch_complete",
    }

    GAS_TYPES = {
        2: 'СПБТ',
        3: 'ПБА',
    }

    BATCH_TYPES = {
        1: 'l',
        2: 'u',
    }

    DEFAULT_GAS_TYPE = 'Не выбран'

    def __init__(self):
        super().__init__()
        self.client = create_opc_client(settings.OPC_SERVER_URL)
        self._opc_connected = False
        self._truck_type = None
        self._trailer_type = None

    @property
    def truck_type_filter(self):
        """Возвращает готовый фильтр для queryset"""
        if not hasattr(self, '_truck_type_filter'):
            self._truck_type_filter = Q(type__type="Цистерна") | Q(type__type="Седельный тягач")
        return self._truck_type_filter

    @property
    def trailer_type(self):
        if not self._trailer_type:
            self._trailer_type = TrailerType.objects.get(type="Полуприцеп цистерна")
        return self._trailer_type

    def get_opc_value(self, node_key):
        """Получает значение с OPC UA сервера по ключу"""
        node_path = self.OPC_NODE_PATHS.get(node_key)
        if not node_path:
            logger.error(f"Invalid OPC node key: {node_key}")
            return None
        try:
            return self.client.get_node(node_path).get_value()
        except Exception as error:
            logger.error(f"Error getting OPC value for {node_key}: {error}", exc_info=True)
            return None

    def set_opc_value(self, node_key, value):
        """Устанавливает значение в OPC UA сервере по ключу"""
        node_path = self.OPC_NODE_PATHS.get(node_key)
        if not node_path:
            logger.error(f"Invalid OPC node key: {node_key}")

        try:
            node = self.client.get_node(node_path)

            # Получаем текущий тип значения узла
            node_value = node.get_value()

            # Преобразуем value к типу current_value
            if node_value is not None:
                target_type = type(node_value)
                try:
                    if target_type == bool:
                        converted_value = bool(value)
                    elif target_type == int:
                        converted_value = int(value)
                    elif target_type == float:
                        converted_value = float(value)
                    elif target_type == str:
                        converted_value = str(value)
                    else:
                        converted_value = value
                except (ValueError, TypeError):
                    logger.warning(f"Cannot convert {value} to {target_type}, using default")
                    converted_value = target_type()  # Значение по умолчанию для типа
            else:
                converted_value = value

            logger.debug(f"Setting {node_key} to {converted_value} (type: {type(converted_value)})")
            node.set_attribute(ua.AttributeIds.Value, ua.DataValue(converted_value))

        except Exception as error:
            logger.error(f"Error setting OPC value for {node_key}: {error}", exc_info=True)

    def get_transport_numbers(self):
        """Получает список номеров из Интеллекта"""
        try:
            transport_list = get_registration_number_list(INTELLECT_SERVER_LIST[1])
            if not transport_list:
                logger.debug('Машина не определена')
                return []
            return [transport['number'] for transport in transport_list]
        except Exception as e:
            logger.error(f'Ошибка при получении списка номеров: {e}', exc_info=True)
            return []

    def find_transports(self, registration_numbers):
        """Находит грузовик и прицеп по списку номеров"""
        try:
            truck = Truck.objects.filter(
                registration_number__in=registration_numbers
            ).filter(
                self.truck_type_filter
            ).select_related('type').first()

            trailer = Trailer.objects.filter(
                registration_number__in=registration_numbers,
                type=self.trailer_type
            ).first()

            return truck, trailer
        except Exception as e:
            logger.error(f'Ошибка при поиске транспорта: {e}', exc_info=True)
            return None, None

    def create_batch(self, batch_type_code, gas_type_code):
        """Создаёт новую партию"""
        registration_numbers = self.get_transport_numbers()

        if not registration_numbers:
            logger.warning('Список номеров пуст')
            self.set_opc_value("response_batch_create", True)
            return
        logger.debug(f'Список номеров: {registration_numbers}')

        truck, trailer = self.find_transports(registration_numbers)

        if not truck:
            logger.error('Не найден подходящий грузовик')
            self.set_opc_value("stop_batch", True)  # Останавливаем формирование партии
            return

        logger.debug(f'Грузовик: {truck.registration_number}-{truck.type.type}')
        if trailer:
            logger.debug(f'Прицеп: {trailer.registration_number}-{trailer.type.type}')

        try:
            AutoGasBatch.objects.create(
                batch_type=self.BATCH_TYPES.get(batch_type_code),
                truck=truck,
                trailer=trailer if trailer else None,
                is_active=True,
                gas_type=self.GAS_TYPES.get(gas_type_code)
            )

            # Определяем показатель вместимости цистерны
            if truck.type.type == "Цистерна":
                capacity_value = truck.max_gas_volume
            elif truck.type.type == "Седельный тягач" and trailer:
                capacity_value = trailer.max_gas_volume
            else:
                capacity_value = 0.0
                logger.warning(f'Не удалось определить объём ёмкости для {truck.registration_number}')

            if capacity_value:
                self.set_opc_value("truck_capacity", capacity_value)

            self.set_opc_value("response_batch_create", True)
        except Exception as e:
            logger.error(f'Ошибка при создании партии: {e}', exc_info=True)

    def complete_batch(self, batch_data):
        """Завершает текущую активную партию"""
        try:
            AutoGasBatch.objects.filter(is_active=True).update(
                gas_amount=batch_data.get('gas_amount'),
                scale_empty_weight=batch_data.get('truck_empty_weight'),
                scale_full_weight=batch_data.get('truck_full_weight'),
                weight_gas_amount=batch_data.get('weight_gas_amount'),
                is_active=False,
                completed_at=datetime.now(),
            )
            self.set_opc_value("response_batch_complete", True)
        except Exception as e:
            logger.error(f'Ошибка при завершении партии: {e}', exc_info=True)

    def handle(self, *args, **kwargs):
        """Обрабатывает текущую активную партию"""
        try:
            self.client.connect()
            self._opc_connected = True

            # Получаем все значения OPC
            opc_values = {key: self.get_opc_value(key) for key in self.OPC_NODE_PATHS.keys()}

            cache_key = 'autogas_batch_processing'
            cached_data = cache.get(cache_key)
            # Преобразуем словарь в строку для стабильного сравнения
            opc_values_str = ';'.join(f'{k}={opc_values[k]}' for k in sorted(opc_values.keys()))
            has_pending_create = opc_values.get("request_batch_create") and not opc_values.get("response_batch_create")
            has_pending_complete = opc_values.get("request_batch_complete") and not opc_values.get("response_batch_complete")
            cache_timeout = (
                self.PENDING_REQUEST_CACHE_TIMEOUT
                if (has_pending_create or has_pending_complete)
                else self.DEFAULT_CACHE_TIMEOUT
            )

            if opc_values_str == cached_data:
                return

            cache.set(cache_key, opc_values_str, timeout=cache_timeout)

            logger.debug(
                f'Тип партии={opc_values["batch_type_code"]}, '
                f'Тип газа={opc_values["gas_type"]}, '
                f'Запрос создания={opc_values["request_batch_create"]}, '
                f'Запрос завершения={opc_values["request_batch_complete"]}'
            )

            # Обработка создания партии
            if opc_values["request_batch_create"] and not opc_values["response_batch_create"]:
                self.create_batch(opc_values["batch_type_code"], opc_values["gas_type"])

            # Обработка завершения партии
            if opc_values["request_batch_complete"] and not opc_values["response_batch_complete"]:
                self.complete_batch(opc_values)

        except Exception as error:
            logger.error(f'Ошибка в основном цикле: {error}', exc_info=True)
        finally:
            if self._opc_connected:
                disconnect_opc(self.client)
                self._opc_connected = False
