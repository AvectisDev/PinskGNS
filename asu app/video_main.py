import asyncio
import aiohttp
from datetime import datetime, timedelta
import django_video_api
from opcua import Client, ua
from settings import INTELLECT_SERVER_LIST, AUTO_BATCH, RAILWAY_BATCH
from intellect_functions import (separation_string_date, get_registration_number_list, check_on_station,
                                 get_transport_type)

USERNAME = "reader"
PASSWORD = "rfid-device"

# OPC constant
RAILWAY = {
    'tank_weight': 0.0,
    'weight_is_stable': False,
    'last_number': ''
}
AUTO = {
    'weight': 0.0,
    'weight_is_stable': False,
    'mass_total': 0.0,
    'volume_total': 0.0
}


def get_opc_value(addr_str):
    """
    Get value from OPC UA server by address:
    Can look it in Editor.exe(SimpleScada)->Variable-> Double-click on the necessary variable->address
    """
    var = client.get_node(addr_str)
    return var.get_value()


def set_opc_value(addr_str, value):
    """
    Get value from OPC UA server by address:
    Can look it in Editor.exe(SimpleScada)->Variable-> Double-click on the necessary variable->address
    """
    var = client.get_node(addr_str)
    return var.set_attribute(ua.AttributeIds.Value, ua.DataValue(value))


def get_opc_data():
    global RAILWAY, AUTO

    try:
        client.connect()
        print('Connect to OPC server successful')

        if AUTO_BATCH['complete']:
            set_opc_value("ns=4; s=Address Space.PLC_SU2.start_loading_batch", False)
            set_opc_value("ns=4; s=Address Space.PLC_SU2.start_unloading_batch", False)
            AUTO_BATCH['complete'] = False

        # проверка команд на запуск партий
        start_loading_batch = get_opc_value("ns=4; s=Address Space.PLC_SU2.start_loading_batch")
        start_unloading_batch = get_opc_value("ns=4; s=Address Space.PLC_SU2.start_unloading_batch")

        if start_loading_batch:
            AUTO_BATCH['command_start'] = True
            AUTO_BATCH['type'] = 'loading'
        elif start_unloading_batch:
            AUTO_BATCH['command_start'] = True
            AUTO_BATCH['type'] = 'unloading'
        else:
            AUTO_BATCH['command_start'] = False
            AUTO_BATCH['process_step'] = 0

        # проверка команды запуска партии приёмки жд цистерн
        RAILWAY_BATCH['command_start'] = get_opc_value("ns=4; s=Address Space.PLC_SU1.start_loading_batch")

        RAILWAY['tank_weight'] = get_opc_value("ns=4; s=Address Space.PLC_SU1.railway_tank_weight")
        RAILWAY['weight_is_stable'] = get_opc_value("ns=4; s=Address Space.PLC_SU1.railway_tank_weight_is_stable")

        AUTO['weight'] = get_opc_value("ns=4; s=Address Space.PLC_SU2.auto_weight")
        AUTO['weight_is_stable'] = get_opc_value("ns=4; s=Address Space.PLC_SU2.weight_is_stable")
        AUTO['mass_total'] = get_opc_value("ns=4; s=Address Space.PLC_SU2.MicroMotion.Mass_inventory")
        AUTO['volume_total'] = get_opc_value("ns=4; s=Address Space.PLC_SU2.MicroMotion.Volume_inventory")

        print(f'Auto:{AUTO}, Railway:{RAILWAY}')

    except Exception as error:
        print(f'No connection to OPC server: {error}')
    finally:
        client.disconnect()
        print('Disconnect from OPC server')


async def transport_process(transport: dict):
    registration_number = transport['registration_number']
    date, time = separation_string_date(transport['date'])
    is_on_station = check_on_station(transport)

    transport_type = get_transport_type(registration_number)

    if transport_type:
        # проверяем наличие в базе данных транспорт с данным номером
        transport_data = await django_video_api.get_transport(registration_number, transport_type)

        if transport_data:
            transport_data['is_on_station'] = is_on_station
            if is_on_station:
                transport_data['entry_date'] = date
                transport_data['entry_time'] = time
                transport_data['departure_date'] = None
                transport_data['departure_time'] = None
            else:
                transport_data['departure_date'] = date
                transport_data['departure_time'] = time

            result = await django_video_api.update_transport(transport_data, transport_type)
            print(f'{transport_type} with number {transport['registration_number']} update')
        else:
            entry_date = entry_time = departure_date = departure_time = None
            if is_on_station:
                entry_date, entry_time = date, time
            else:
                departure_date, departure_time = date, time

            new_transport_data = {
                'registration_number': registration_number,
                'entry_date': entry_date,
                'entry_time': entry_time,
                'departure_date': departure_date,
                'departure_time': departure_time,
                'is_on_station': is_on_station
            }
            result = await django_video_api.create_transport(new_transport_data, transport_type)
            print(f'{transport_type} with number {transport['registration_number']} create')
        return result
    else:
        return None


async def auto_batch_processing(server):
    """
    Формирование и обработка партий приёмки/отгрузки газа в автоцистернах
    """

    match AUTO_BATCH['process_step']:
        case 1:  # Поиск машины в базе. Создание партии
            transport_list = await get_registration_number_list(server)

            if not transport_list:
                print('Автоколонка. Машина не определена')
                return

            for transport in reversed(transport_list):  # начинаем с последней определённой машины
                registration_number = transport['registration_number']
                transport_type = get_transport_type(registration_number)

                if transport_type == 'truck' and not AUTO_BATCH['truck_id']:
                    print(f'Машина на весах. Номер - {registration_number}')

                    # запрос данных по текущему номеру машины
                    truck_data = await django_video_api.get_transport(registration_number, transport_type)

                    if truck_data:
                        AUTO_BATCH['truck_id'] = truck_data['id']

                if transport_type == 'trailer' and not AUTO_BATCH['trailer_id']:
                    print(f'Прицеп на весах. Номер - {registration_number}')

                    # запрос данных по текущему номеру машины
                    trailer_data = await django_video_api.get_transport(registration_number, transport_type)

                    if trailer_data:
                        AUTO_BATCH['trailer_id'] = trailer_data['id']

            batch_data = {
                'batch_type': 'l' if AUTO_BATCH['type'] == 'loading' else 'u',
                'truck': AUTO_BATCH['truck_id'],
                'trailer': 0 if not AUTO_BATCH['trailer_id'] else AUTO_BATCH['trailer_id'],
                'is_active': True
            }

            # начинаем партию
            batch_data = await django_video_api.create_batch_gas(batch_data)
            AUTO_BATCH['batch_id'] = batch_data['id']
            AUTO_BATCH['process_step'] = 2

        case 2:  # Взвешивание машины/сохранение начального веса и показания массомера
            print('Автоколонка. Шаг 2')
            if AUTO['weight_is_stable']:
                if AUTO_BATCH['type'] == 'loading':
                    AUTO_BATCH['truck_full_weight'] = AUTO['weight']
                elif AUTO_BATCH['type'] == 'unloading':
                    AUTO_BATCH['truck_empty_weight'] = AUTO['weight']

                AUTO_BATCH['initial_mass_meter'] = AUTO['volume_total']

                batch_data = {
                    'id': AUTO_BATCH['batch_id'],
                    'scale_full_weight': AUTO_BATCH['truck_full_weight'],
                    'scale_empty_weight': AUTO_BATCH['truck_empty_weight']
                }

                batch_data = await django_video_api.update_batch_gas(batch_data)
                print(batch_data)
                AUTO_BATCH['process_step'] = 3

        case 3:
            print('Автоколонка. Шаг 3')
            if AUTO['weight_is_stable'] and AUTO_BATCH['initial_mass_meter'] != AUTO['volume_total']:

                if AUTO_BATCH['type'] == 'loading':
                    AUTO_BATCH['truck_empty_weight'] = AUTO['weight']
                elif AUTO_BATCH['type'] == 'unloading':
                    AUTO_BATCH['truck_full_weight'] = AUTO['weight']

                AUTO_BATCH['final_mass_meter'] = AUTO['volume_total']

                batch_data = {
                    'id': AUTO_BATCH['batch_id'],
                    'scale_full_weight': AUTO_BATCH['truck_full_weight'],
                    'scale_empty_weight': AUTO_BATCH['truck_empty_weight'],
                    'gas_amount': AUTO_BATCH['final_mass_meter'] - AUTO_BATCH['initial_mass_meter'],
                    'weight_gas_amount': AUTO_BATCH['truck_full_weight'] - AUTO_BATCH['truck_empty_weight'],
                    'is_active': False
                }

                # завершаем партию приёмки газа
                await django_video_api.update_batch_gas(batch_data)

                AUTO_BATCH['start_flag'] = False
                AUTO_BATCH['complete'] = True

        case _:  # Запуск процесса обработки партии при наличии команды
            if AUTO_BATCH['command_start'] and not AUTO_BATCH['start_flag']:
                AUTO_BATCH['process_step'] = 1
                AUTO_BATCH['start_flag'] = True

                print('Начало партии приёмки автоцистерн')


async def kpp_processing(server: dict):
    print('Обработка регистрационных номеров на КПП')

    # получаем от "Интеллекта" список номеров с данными фотофиксации
    transport_list = await get_registration_number_list(server)

    # Задачи для обработки регистрационных номеров на КПП
    for transport in transport_list:
        await transport_process(transport)


async def railway_processing(server: dict):
    print('Обработка жд цистерн')

    if RAILWAY['weight_is_stable']:
        weight = RAILWAY['tank_weight']

        # получаем от "Интеллекта" список номеров с данными фотофиксации
        railway_tank_list = await get_registration_number_list(server)

        if not railway_tank_list:
            print('ЖД весовая. Цистерна не определена')
            return

        # работаем с номером последней цистерны
        railway_tank_data = railway_tank_list[-1]
        if railway_tank_data['registration_number'] != RAILWAY['last_number']:
            RAILWAY['last_number'] = railway_tank_data['registration_number']
            railway_tank = await transport_process(railway_tank_data)

            if railway_tank['is_on_station']:
                railway_tank['full_weight'] = weight
            else:
                railway_tank['gas_weight'] = railway_tank['full_weight'] - weight
                railway_tank['empty_weight'] = weight

            await django_video_api.update_transport(railway_tank, 'railway_tank')
        print(f'ЖД весовая. Цистерна № {RAILWAY['last_number']} на весах. Вес = {weight} тонн')


async def periodic_kpp_processing():
    while True:
        # Задачи обработки номеров на КПП. Сервера 4 и 5
        await kpp_processing(INTELLECT_SERVER_LIST[2])
        await asyncio.sleep(60)  # 60 секунд = 1 минута


async def periodic_railway_processing():
    while True:
        # Задачи обработки жд цистерн. Сервер 1
        await railway_processing(INTELLECT_SERVER_LIST[0])
        await asyncio.sleep(2)


async def main():
    kpp_task = asyncio.create_task(periodic_kpp_processing())
    railway_task = asyncio.create_task(periodic_railway_processing())

    while True:
        # Обработка данных OPC сервера
        get_opc_data()

        # Обработка процессов приёмки/отгрузки газа в автоцистернах
        await auto_batch_processing(INTELLECT_SERVER_LIST[1])
        await asyncio.sleep(2)


if __name__ == "__main__":
    client = Client("opc.tcp://127.0.0.1:4841")
    asyncio.run(main())
