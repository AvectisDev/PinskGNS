import asyncio
import db
import binascii
from datetime import datetime
from settings import READER_LIST, COMMANDS
import balloon_api
import logging
from concurrent.futures import ThreadPoolExecutor


logging.basicConfig(
    level=logging.INFO,  # Уровень логирования
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='rfid_app.log',
    filemode='w',
    encoding='utf-8'
)

logger = logging.getLogger('app_logger')
logger.setLevel(logging.DEBUG)


async def data_exchange_with_reader(controller: dict, command: str):
    """
    Асинхронная функция выполняет обмен данными со считывателем FEIG.
    Отправляет запрос и возвращает полный буфер данных со считывателя.
    """
    reader, writer = await asyncio.open_connection(controller['ip'], controller['port'])
    try:
        writer.write(binascii.unhexlify(COMMANDS[command]))
        await writer.drain()

        data = await asyncio.wait_for(reader.read(2048), timeout=1)
        buffer = binascii.hexlify(data).decode()
        return buffer
    except asyncio.TimeoutError:
        logger.error(f'Таймаут при ожидании ответа от контроллера {controller["ip"]}:{controller["port"]}')
        return []
    except Exception as error:
        logger.debug(f'Нет связи с контроллером {controller["ip"]}:{controller["port"]}: {error}')
        return []
    finally:
        writer.close()
        await writer.wait_closed()


def byte_reversal(byte_string: str):
    """
    Функция разворачивает принятые со считывателя байты в обратном порядке, меняя местами первый и последний байт,
    второй и предпоследний и т.д.
    """
    data_list = list(byte_string)
    k = -1
    for i in range((len(data_list)) // 2):
        data_list[i], data_list[k] = data_list[k], data_list[i]
        k -= 1
    for i in range(0, len(data_list) - 1, 2):
        data_list[i], data_list[i + 1] = data_list[i + 1], data_list[i]
    return ''.join(data_list)


def work_with_nfc_tag_list(nfc_tag: str, nfc_tag_list: list):
    """
    Функция кэширует 5 последних считанных меток и определяет, есть ли в этом списке следующая считанная метка.
    Если метки нет в списке, то добавляет новую метку, если метка есть (повторное считывание), до пропускаем все
    последующие действия с ней
    """
    if nfc_tag not in nfc_tag_list:
        if len(nfc_tag_list) > 5:
            nfc_tag_list.pop(0)
            nfc_tag_list.append(nfc_tag)
        else:
            nfc_tag_list.append(nfc_tag)


async def balloon_passport_processing(nfc_tag: str, reader: dict):
    """
    Функция проверяет наличие и заполненность паспорта в базе данных. Перезаписывает статус баллона в зависимости от
    того, через какой считыватель сейчас прошёл баллон.
    """

    passport = {
        'nfc_tag': nfc_tag,
        'status': reader['status'],
        'reader_number': reader['number'],
        'reader_function': reader['function']
    }

    # Обновляем статус баллона в базе данных. Если паспорта нет - создаём запись
    passport = await balloon_api.update_balloon(passport)

    return passport['filling_status']


async def read_nfc_tag(reader: dict):
    """
    Асинхронная функция отправляет запрос на считыватель FEIG и получает в ответ дату, время и номер RFID метки.
    """
    # Проверяем состояние входов считывателя
    reader['input_state'] = await read_input_status(reader)
    
    # Запрос номера метки в буфере считывателя
    data = await data_exchange_with_reader(reader, 'read_last_item_from_buffer')

    # if reader["ip"] == '10.10.2.23':
        # logger.debug(f'{reader["ip"]} rfid 1.чтение метки из буфера. Данные - {data}')

    if len(data) > 24:  # если со считывателя пришли данные с меткой
        nfc_tag = byte_reversal(data[32:48])

        # if reader["ip"] == '10.10.2.23':
        #     logger.debug(f'{reader["ip"]} rfid 2.номер rfid метки = {nfc_tag}, список предыдущих меток = {reader['previous_nfc_tags']}')

        # метка отличается от недавно считанных и заканчивается на "e0"
        if nfc_tag not in reader['previous_nfc_tags'] and nfc_tag.endswith("e0"):
            # сохраняем метку в кэше считанных меток
            work_with_nfc_tag_list(nfc_tag, reader['previous_nfc_tags'])

            try:
                balloon_passport_status = await balloon_passport_processing(nfc_tag, reader)
                
                # if reader["ip"] == '10.10.2.23':
                #     logger.debug(f'{reader["ip"]} rfid 3.записываем в бд новое количество rfid баллонов')

                # data_for_amount = {
                #     'reader_id': reader['number'],
                #     'reader_status': reader['status']
                # }
                # await balloon_api.update_balloon_amount('rfid', data_for_amount)
                await db.write_balloons_amount(reader, 'rfid')  # сохраняем значение в бд

                # if reader["ip"] == '10.10.2.23':
                #     logger.debug(f'{reader["ip"]} rfid 4.запись завершена')

                if balloon_passport_status:  # если паспорт заполнен
                    # зажигаем зелёную лампу на считывателе
                    await data_exchange_with_reader(reader, 'read_complete')
                else:
                    # мигание зелёной лампы на считывателе
                    await data_exchange_with_reader(reader, 'read_complete_with_error')

            except Exception as error:
                print('Ошибка в функции read_nfc_tag', error)

    else:
        await asyncio.sleep(0.3)

    # очищаем буферную память считывателя
    await data_exchange_with_reader(reader, 'clean_buffer')


async def read_input_status(reader: dict):
    """
    Функция отправляет запрос на считыватель FEIG и получает в ответ состояние дискретных входов
    """
    # присваиваем предыдущее состояние входа временной переменной
    previous_input_state = reader['input_state']

    data = await data_exchange_with_reader(reader, 'inputs_read')
    # if reader["ip"] == '10.10.2.23':
    #     logger.debug(f'{reader["ip"]} 1. чтение состояний входов. Данные - {data}')

    if len(data) == 18:
        input_state = int(data[13])  # определяем состояние 1-го входа (13 индекс в ответе)
        # if reader["ip"] == '10.10.2.23':
        #     logger.debug(f'{reader["ip"]} 2.состояние 1-го входа = {input_state}, предыдущее = {previous_input_state}')

        if input_state == 1 and previous_input_state == 0:
            # if reader["ip"] == '10.10.2.23':
            #     logger.debug(f'{reader["ip"]} 3.записываем в бд новое количество определённых баллонов')

            # data_for_amount = {
            #     'reader_id': reader['number'],
            #     'reader_status': reader['status']
            # }
            # await balloon_api.update_balloon_amount('sensor', data_for_amount)
            await db.write_balloons_amount(reader, 'sensor')

            # if reader["ip"] == '10.10.2.23':
            #     logger.debug(f'{reader["ip"]} 4.запись завершена')

            return 1  # возвращаем состояние входа "активен"
        elif input_state == 0 and previous_input_state == 1:
            return 0  # возвращаем состояние входа "неактивен"
        else:
            return previous_input_state
    else:
        return previous_input_state


def process_reader_sync(reader):
    asyncio.run(process_reader(reader))


async def process_reader(reader):
    while True:
        try:
            await read_nfc_tag(reader)
        except Exception as error:
            logger.error(f"Error in process_reader: {error}")


async def main():
    # При запуске программы очищаем буфер считывателей
    tasks = [asyncio.create_task(data_exchange_with_reader(reader, 'clean_buffer')) for reader in READER_LIST]
    print('Очистка буфера RFID-считывателей...')
    await asyncio.wait(tasks)

    with ThreadPoolExecutor(max_workers=len(READER_LIST)) as executor:
        print('Программа в работе')
        loop = asyncio.get_running_loop()
        tasks = [loop.run_in_executor(executor, process_reader_sync, reader) for reader in READER_LIST]
        await asyncio.gather(*tasks)


if __name__ == "__main__":
    print('Запуск программы считывания RFID-меток...')
    asyncio.run(main())
