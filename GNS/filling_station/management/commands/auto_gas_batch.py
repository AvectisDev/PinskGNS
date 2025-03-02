import logging
from opcua import Client, ua
from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned
from django.core.management.base import BaseCommand
from datetime import datetime
from filling_station.models import AutoGasBatch, Truck, TruckType, Trailer, TrailerType
from .intellect import get_registration_number_list, INTELLECT_SERVER_LIST, get_transport_type

logger = logging.getLogger('filling_station')


class Command(BaseCommand):
    def __init__(self):
        super().__init__()
        self.client = Client("opc.tcp://host.docker.internal:4841")
        # self.client = Client("opc.tcp://127.0.0.1:4841")

    def get_opc_value(self, addr_str):
        """Получить значение с OPC UA сервера по адресу."""
        var = self.client.get_node(addr_str)
        return var.get_value()

    def set_opc_value(self, addr_str, value):
        """Установить значение на OPC UA сервере по адресу."""
        var = self.client.get_node(addr_str)
        return var.set_attribute(ua.AttributeIds.Value, ua.DataValue(value))

    def get_gas_type(self, gas_type):
        if gas_type == 2:
            return 'СПБТ'
        elif gas_type == 3:
            return 'ПБА'
        else:
            return 'Не выбран'

    def batch_create(self, batch_type, from_opc_gas_type):
        try:
            logger.debug('Автовесовая. Запрос определения номера. Начало партии приёмки')

            # Поиск машины в базе Интеллект
            transport_list = get_registration_number_list(INTELLECT_SERVER_LIST[1])
            logger.debug(f'Автовесовая. Список номеров: {transport_list}')

            if not transport_list:
                logger.debug('Автоколонка. Машина не определена')
                return

            # формируем список считанных номеров для фильтрации по базе
            registration_number_list = [transport['number'] for transport in transport_list]

            # Находим объект TruckType с типом "Цистерна" и объект TrailerType с типом "Полуприцеп цистерна"
            truck_type = TruckType.objects.get(type="Цистерна")
            trailer_type = TrailerType.objects.get(type="Полуприцеп цистерна")

            auto_batch_truck = Truck.objects.filter(
                registration_number__in=registration_number_list,
                type=truck_type).first()
            auto_batch_trailer = Trailer.objects.filter(
                registration_number__in=registration_number_list,
                type=trailer_type).first()

            logger.debug(f'Номер грузовика - {auto_batch_truck.registration_number}. '
                         f'Номер прицепа - {auto_batch_trailer.registration_number}')

            batch_gas_type = self.get_gas_type(from_opc_gas_type)

            # Создаём партию
            AutoGasBatch.objects.create(
                batch_type='l' if batch_type == 'loading' else 'u',
                truck=auto_batch_truck.id,
                trailer=auto_batch_trailer.id if auto_batch_trailer else 0,
                is_active=True,
                gas_type=batch_gas_type
            )

            # Маркер завершения создания партии
            self.set_opc_value("ns=4; s=Address Space.PLC_SU2.batch.response_number_detect", True)

        except Exception as error:
            logger.error(f'Автоколонка. ошибка в функции batch_create - {error}')

    def handle(self, *args, **kwargs):
        try:
            self.client.connect()
            logger.info('Connect to OPC server successful')

            batch_type = self.get_opc_value("ns=4; s=Address Space.PLC_SU2.batch.batch_type")
            gas_type = self.get_opc_value("ns=4; s=Address Space.PLC_SU2.batch.gas_type")

            initial_mass_meter = self.get_opc_value("ns=4; s=Address Space.PLC_SU2.batch.initial_mass_meter")
            final_mass_meter = self.get_opc_value("ns=4; s=Address Space.PLC_SU2.batch.final_mass_meter")
            gas_amount = self.get_opc_value("ns=4; s=Address Space.PLC_SU2.batch.gas_amount")

            truck_full_weight = self.get_opc_value("ns=4; s=Address Space.PLC_SU2.batch.truck_full_weight")
            truck_empty_weight = self.get_opc_value("ns=4; s=Address Space.PLC_SU2.batch.truck_empty_weight")
            weight_gas_amount = self.get_opc_value("ns=4; s=Address Space.PLC_SU2.batch.weight_gas_amount")

            request_batch_create = self.get_opc_value("ns=4; s=Address Space.PLC_SU2.batch.request_number_identification")
            response_batch_create = self.get_opc_value("ns=4; s=Address Space.PLC_SU2.batch.response_number_detect")
            request_batch_complete = self.get_opc_value("ns=4; s=Address Space.PLC_SU2.batch.request_batch_complete")
            response_batch_complete = self.get_opc_value("ns=4; s=Address Space.PLC_SU2.batch.response_batch_complete")

            logger.info(f'batch_type={batch_type}, gas_type={gas_type},'
                        f'request_number_identification={request_batch_create}, '
                        f'request_batch_complete={request_batch_complete}')

            # Создание партии
            if request_batch_create and not response_batch_create:
                self.batch_create(batch_type, gas_type)

            # Завершение партии
            if request_batch_complete and not response_batch_complete:
                current_date = datetime.now()

                AutoGasBatch.objects.filter(is_active=True).update(
                    gas_amount=gas_amount,
                    scale_empty_weight=truck_empty_weight,
                    scale_full_weight=truck_full_weight,
                    weight_gas_amount=weight_gas_amount,
                    is_active=False,
                    end_date=current_date.date(),
                    end_time=current_date.time()
                )
                # Маркер завершения партии
                self.set_opc_value("ns=4; s=Address Space.PLC_SU2.batch.response_batch_complete", True)

        except Exception as error:
            logger.error(f'No connection to OPC server: {error}')
        finally:
            self.client.disconnect()
            logger.info('Disconnect from OPC server')
