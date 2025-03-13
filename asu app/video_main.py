import asyncio
import logging
from opcua import Client, ua
from filling_station.management.commands.intellect import (separation_string_date, get_registration_number_list, check_on_station,
                                                           get_transport_type)


async def transport_process(transport: dict):
    registration_number = transport['registration_number']
    date, time = separation_string_date(transport['date'])
    is_on_station = check_on_station(transport)

    # Определяем тип т/с
    transport_type = get_transport_type(registration_number)

    if transport_type:
        # проверяем наличие в базе данных транспорт с данным номером
        transport_data = await video_api.get_transport(registration_number, transport_type)

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

            result = await video_api.update_transport(transport_data, transport_type)
            logger.warning(f'{transport_type} with number {transport['registration_number']} update')

        else:
            # создаём в базе только записи для жд цистерн (временно, пока не настроят камеры на КПП)
            if transport_type == 'railway_tank':

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
                result = await video_api.create_transport(new_transport_data, transport_type)
                logger.warning(f'{transport_type} with number {transport['registration_number']} create')
        return result
    else:
        return None


async def auto_batch_processing(server):
    """
    Формирование и обработка партий приёмки/отгрузки газа в автоцистернах
    """

    # Поиск машины в базе. Создание партии
    if AUTO['request_number_identification'] and not AUTO['response_number_detect']:
        try:
            logger.warning('Автовесовая. Запрос определения номера. Начало партии приёмки')

            transport_list = await get_registration_number_list(server)
            logger.warning(f'Автовесовая. Список номеров: {transport_list}')

            if not transport_list:
                logger.warning('Автоколонка. Машина не определена')
                return

            for transport in reversed(transport_list):  # начинаем с последней определённой машины

                registration_number = transport['registration_number']
                transport_type = get_transport_type(registration_number)
                logger.warning(f'Номер - {registration_number}. Тип - {transport_type}')
                if transport_type == 'truck' and not AUTO['truck_id']:
                    logger.warning(f'Автоколонка. Машина на весах. Номер - {registration_number}')

                    # запрос данных по текущему номеру машины
                    logger.warning(f'Автоколонка. запрос данных по текущему номеру машины')
                    truck_data = await video_api.get_transport(registration_number, transport_type)
                    logger.warning(f'Автоколонка. запрос данных по текущему номеру машины выполнен')
                    if truck_data and truck_data.get('type') == 'Цистерна':
                        AUTO['truck_id'] = truck_data.get('id')

                if transport_type == 'trailer' and not AUTO['trailer_id']:
                    logger.warning(f'Автоколонка. Прицеп на весах. Номер - {registration_number}')

                    # запрос данных по текущему номеру прицепа
                    logger.warning(f'Автоколонка. запрос данных по текущему номеру прицепа')
                    trailer_data = await video_api.get_transport(registration_number, transport_type)
                    logger.warning(f'Автоколонка. запрос данных по текущему номеру прицепа выполнен')
                    if trailer_data and trailer_data.get('type') == 'Полуприцеп цистерна':
                        AUTO['trailer_id'] = trailer_data.get('id')
            logger.warning(f'Автоколонка. Выходим из цикла проверки номеров')
            if AUTO['gas_type'] == 2:
                gas_type = 'СПБТ'
            elif AUTO['gas_type'] == 3:
                gas_type = 'ПБА'
            else:
                gas_type = 'Не выбран'

            batch_data = {
                'batch_type': 'l' if AUTO['batch_type'] == 'loading' else 'u',
                'truck': AUTO['truck_id'],
                'trailer': 0 if not AUTO['trailer_id'] else AUTO['trailer_id'],
                'is_active': True,
                'gas_type': gas_type
            }

            # начинаем партию
            logger.warning(f'Автоколонка. Запрос создания партии. Данные - {batch_data}')
            batch_data = await video_api.create_batch_gas(batch_data)
            AUTO['batch_id'] = batch_data.get('id')
            AUTO['response_number_detect'] = True
        except Exception as error:
            logger.error(f'Автоколонка. response_number_detect - {error}')

    if AUTO['request_batch_complete']:
        try:
            batch_data = {
                'is_active': False,
                'initial_mass_meter': AUTO['initial_mass_meter'],
                'final_mass_meter': AUTO['final_mass_meter'],
                'gas_amount': AUTO['gas_amount'],
                'truck_full_weight': AUTO['truck_full_weight'],
                'truck_empty_weight': AUTO['truck_empty_weight'],
                'weight_gas_amount': AUTO['weight_gas_amount'],
            }
            # завершаем партию приёмки газа
            logger.warning(f'Автоколонка. Запрос редактирования партии. Данные - {batch_data}')
            await video_api.update_batch_gas(AUTO['batch_id'], batch_data)
            AUTO['response_batch_complete'] = True
        except Exception as error:
            logger.error(f'Автоколонка. response_batch_complete - {error}')

async def kpp_processing(server: dict):
    logger.warning('Обработка регистрационных номеров на КПП')

    # получаем от "Интеллекта" список номеров с данными фотофиксации
    transport_list = await get_registration_number_list(server)

    # Задачи для обработки регистрационных номеров на КПП
    for transport in transport_list:
        await transport_process(transport)


async def periodic_kpp_processing():
    while True:
        # Задачи обработки номеров на КПП. Сервера 4 и 5
        try:
            await kpp_processing(INTELLECT_SERVER_LIST[2])
            await asyncio.sleep(60)  # 60 секунд = 1 минута
        except Exception as error:
            logger.error(f'КПП: {error}')



async def main():
    kpp_task = asyncio.create_task(periodic_kpp_processing())
    railway_task = asyncio.create_task(periodic_railway_processing())

    while True:
        # Обработка данных OPC сервера
        get_opc_data()

        # Обработка процессов приёмки/отгрузки газа в автоцистернах
        try:
            await auto_batch_processing(INTELLECT_SERVER_LIST[1])
            await asyncio.sleep(5)
        except Exception as error:
            logger.error(f'Автоколонка: {error}')


if __name__ == "__main__":
    client = Client("opc.tcp://127.0.0.1:4841")
    # client = Client("opc.tcp://host.docker.internal:4841") # for work with docker
    asyncio.run(main())
