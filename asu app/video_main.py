import asyncio
import aiohttp
import schedule
from datetime import datetime, timedelta
import django_video_api
from opcua import Client
from setting import INTELLECT_URL, INTELLECT_SERVER_LIST, GAS_LOADING_BATCH, GAS_UNLOADING_BATCH

USERNAME = "reader"
PASSWORD = "rfid-device"

# OPC constant
RAILWAY = {
    'tank_weight': 0.0,
    'weight_is_stable': False,
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
    client = Client("opc.tcp://127.0.0.1:4841")
    var = client.get_node(addr_str)
    return var.get_value()


def get_opc_data():
    global RAILWAY, AUTO
    client = Client("opc.tcp://127.0.0.1:4841")
    try:
        client.connect()
        print('Connect to OPC server successful')

        RAILWAY['tank_weight'] = get_opc_value("ns=4; s=Address Space.PLC_SU1.railway_tank_weight")
        RAILWAY['weight_is_stable'] = get_opc_value("ns=4; s=Address Space.PLC_SU1.railway_tank_weight_is_stable")

        AUTO['weight'] = get_opc_value("ns=4; s=Address Space.PLC_SU2.auto_weight")
        AUTO['weight_is_stable'] = get_opc_value("ns=4; s=Address Space.PLC_SU2.weight_is_stable")
        AUTO['mass_total'] = get_opc_value("ns=4; s=Address Space.PLC_SU2.MicroMotion.Mass_total")
        AUTO['volume_total'] = get_opc_value("ns=4; s=Address Space.PLC_SU2.MicroMotion.Volume_total")

        print(RAILWAY, AUTO)

    except Exception as e:
        print('No connection to OPC server:', e)
    finally:
        client.disconnect()
        print('Disconnect from OPC server')


async def get_intellect_data(data):
    """
    Функция посылает запрос в "Интеллект" и возвращает статус запроса и список словарей с записями о транспорте
    data: словарь с данными для запроса
    return: кортеж -
             True и JSON-ответ при успешном запросе;
             False и код статуса при ошибке
    """
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(INTELLECT_URL, json=data, timeout=1) as response:
                response.raise_for_status()  # Вызывает исключение для ошибок HTTP

                return True, await response.json()

        except (aiohttp.ClientError, asyncio.TimeoutError) as error:
            return False, error


async def get_start_time(delta_minutes: int) -> str:
    """
    Функция определяет время, начиная с которого нужно запросить данные в базе данных "Интеллект".
    delta_minutes: числовое значение количества минут, которые будут отниматься от текущего времени.
    Дополнительно нужно отнять 3 часа, т.к. "Интеллект" выдаёт данные по часовому поясу UTC+0
    return: string - для передачи в формате JSON объект времени конвертируется в строку под формат "Интеллект"
    """
    start_date = datetime.now() - timedelta(hours=3, minutes=delta_minutes)
    start_date_string = f'{start_date.strftime("%Y-%m-%dT%H:%M:%S")}.000'
    return start_date_string


async def separation_string_date(date_string: str = '') -> tuple:
    """
    Функция преобразует время, полученное из "Интеллект", в кортеж строк (дата, время) для передачи в JSON
    Дополнительно нужно прибавить 3 часа, т.к. "Интеллект" выдаёт данные по часовому поясу UTC+0
    time_string: строчное представление времени, полученное из "Интеллект"
    return: кортеж из строк - (дата, время)
    """
    try:
        converted_time = datetime.strptime(date_string, "%d.%m.%Y %H:%M:%S") + timedelta(hours=3)
        string_date = converted_time.strftime("%Y-%m-%d")
        string_time = converted_time.strftime("%H:%M")
    except ValueError as e:
        raise ValueError(f"Invalid date format: {str(e)}")
    return string_date, string_time


async def get_registration_number_list(server: dict) -> list:
    """
    Функция формирует тело запроса к базе данных "Интеллект".
    Возвращает номер и дату прибывших/убывших машин и прицепов в виде списка словарей.
    """

    data_for_request = {
        "id": server['id'],
        "time_from": await get_start_time(server['delta_minutes']),
        "numbers_operation": "OR"
    }
    status, intellect_data = await get_intellect_data(data_for_request)

    item_list = intellect_data['Protocols'] if 'Protocols' in intellect_data else []
    out_list = []
    if status and len(item_list) > 0:

        for item in item_list:
            out_list.append({
                'registration_number': item['number'],
                'date': item['date'],
                'direction': item['direction']
            })

    return out_list


async def check_on_station(server: dict, direction) -> bool:
    """
    Функция обрабатывает направление движения транспорта, определённое "Интеллектом", и возвращает статус
    return:
        True - транспорт въёхал на территорию ГНС
        False - транспорт выехал с территории ГНС
    """
    if server['id'] == '4' and direction == '1':
        return True
    if server['id'] == '4' and direction == '2':
        return False
    if server['id'] == '5' and direction == '2':
        return True
    if server['id'] == '5' and direction == '1':
        return False


async def get_transport_type(registration_number: str) -> str:
    """
    Функция по номеру транспорта определяет его вид:
    - если номер начинается с цифры, значит это легковая машина - пропускаем обработку
    - если номер начинается с 2-х букв, значит это грузовик, иначе - прицеп
    """

    if registration_number[0].isdigit():
        return ''

    if registration_number[0:2].isalpha():
        return 'truck'
    else:
        return 'trailer'


async def kpp_processing(server: dict):
    print('start truck_processing')

    # получаем от "Интеллекта" список номеров с данными фотофиксации
    transport_list = await get_registration_number_list(server)
    for transport in transport_list:

        registration_number = transport['registration_number']
        date, time = await separation_string_date(transport['date'])
        is_on_station = await check_on_station(server, transport['direction'])

        transport_type = await get_transport_type(registration_number)

        if transport_type:
            # проверяем наличие в базе данных транспорт с данным номером
            transport_found, transport_data = await django_video_api.get_transport(registration_number, transport_type)

            if transport_found:
                for item in transport_data:
                    item['is_on_station'] = is_on_station
                    if is_on_station:
                        item['entry_date'] = date
                        item['entry_time'] = time
                        item['departure_date'] = None
                        item['departure_time'] = None
                    else:
                        item['departure_date'] = date
                        item['departure_time'] = time

                    await django_video_api.update_transport(item, transport_type)
                    print(f'{transport_type} with number {transport['registration_number']} update')
            else:
                new_transport_data = {
                    'registration_number': registration_number,
                    'entry_date': date,
                    'entry_time': time,
                    'is_on_station': is_on_station
                }
                await django_video_api.create_transport(new_transport_data, transport_type)
                print(f'{transport_type} with number {transport['registration_number']} create')


async def gas_loading_processing(server):
    """

    """
    if GAS_LOADING_BATCH['command_start'] and not GAS_LOADING_BATCH['start_flag']:
        loading_step = 1
        print('Начало партии приёмки автоцистерн')
        GAS_LOADING_BATCH['start_flag'] = True

    if not GAS_LOADING_BATCH['start_flag']:
        return

    match loading_step:
        case 1:  # Поиск машины в базе. Создание партии
            transport_list = await get_registration_number_list(server)

            if not transport_list:
                print('Машина не определена')
                return

            for transport in reversed(transport_list):  # начинаем с последней определённой машины
                registration_number = transport['registration_number']
                transport_type = await get_transport_type(registration_number)

                if transport_type == 'truck':
                    print(f'Машина на весах. Номер - {registration_number}')

                    # запрос данных по текущему номеру машины
                    transport_found, transport_data = await django_video_api.get_transport(registration_number, transport_type)

                    if transport_found:
                        GAS_LOADING_BATCH['truck_id'] = transport_data[0]['id']
                        loading_step = 2

                        batch_data = {
                            'truck': GAS_LOADING_BATCH['truck_id'],
                            'trailer': 0,
                            'is_active': True
                        }
                        await django_video_api.create_batch_gas(batch_data)  # начинаем партию приёмки газа

                    # Если был обработан грузовик, то завершаем цикл
                    break

        case 2:  # Взвешивание машины/сохранение начального веса и показания массомера
            if AUTO['weight_is_stable']:
                GAS_LOADING_BATCH['truck_full_weight'] = AUTO['weight']
                GAS_LOADING_BATCH['initial_mass_meter'] = AUTO['mass_total']

                truck_data = {
                    'id': GAS_LOADING_BATCH['truck_id'],
                    'full_weight': GAS_LOADING_BATCH['truck_full_weight']
                }

                await django_video_api.update_transport(truck_data, 'truck')

                print(
                    f'Вес полной машины = {GAS_LOADING_BATCH['truck_full_weight']}. Начальные показания массомера {GAS_LOADING_BATCH['initial_mass_meter']}')
                loading_step = 3

        case 3:
            if AUTO['weight_is_stable'] and GAS_LOADING_BATCH['initial_mass_meter'] != AUTO['mass_total']:
                GAS_LOADING_BATCH['truck_empty_weight'] = AUTO['weight']
                GAS_LOADING_BATCH['final_mass_meter'] = AUTO['mass_total']

                truck_data = {
                    'id': GAS_LOADING_BATCH['truck_id'],
                    'empty_weight': GAS_LOADING_BATCH['truck_empty_weight']
                }

                await django_video_api.update_transport(truck_data, 'truck')

                batch_found, batch_data = await django_video_api.get_batch_gas()
                if batch_found:
                    batch_data['gas_amount'] = GAS_LOADING_BATCH['final_mass_meter'] - GAS_LOADING_BATCH['initial_mass_meter']
                    batch_data['weight_gas_amount'] = GAS_LOADING_BATCH['truck_full_weight'] - GAS_LOADING_BATCH['truck_empty_weight']
                    batch_data['is_active'] = False

                    await django_video_api.update_batch_gas(batch_data)  # завершаем партию приёмки газа

                print(f'Вес пустой машины = {GAS_LOADING_BATCH['truck_empty_weight']}. Последние показания массомера {GAS_LOADING_BATCH['final_mass_meter']}')
                loading_step = 0


async def main():
    while True:
        # schedule.run_pending()
        # Задачи обработки номеров на КПП. Сервера 4 и 5
        await kpp_processing(INTELLECT_SERVER_LIST[2])

        await asyncio.sleep(5)

        # Обработка данных OPC сервера

        # get_opc_data()
        await gas_loading_processing(INTELLECT_SERVER_LIST[1])


# schedule.every(1).minutes.do(kpp_processing)
# schedule.every(10).seconds.do(truck_processing)

if __name__ == "__main__":
    asyncio.run(main())
