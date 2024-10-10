import asyncio
import socket
import db
import binascii
from settings import READER_LIST, COMMANDS
from miriada import get_balloon_by_nfc_tag as get_balloon
import django_balloon_api


async def data_exchange_with_reader(controller: dict, command: str):
    """
    Асинхронная функция выполняет обмен данными со считывателем FEIG.
    Отправляет запрос и возвращает полный буфер данных со считывателя.
    """
    loop = asyncio.get_event_loop()

    def sync_data_exchange():
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.settimeout(1)
                s.connect((controller['ip'], controller['port']))
                s.sendall(binascii.unhexlify(COMMANDS[command]))  # команда считывания метки

                data = s.recv(2048)
                buffer = binascii.hexlify(data).decode()
                print(f'Receive complete. Data from {controller["ip"]}:{controller["port"]}: {buffer}')
                return buffer
            except Exception as error:
                print(f'Can`t establish connection with RFID reader {controller["ip"]}:{controller["port"]}: {error}')
                return []

    return await loop.run_in_executor(None, sync_data_exchange)


def byte_reversal(byte_string: str):
    """
    Функция разворачивает принятые со считывателя байты в обратном порядке, меняя местами первый и последний байт,
    второй и предпоследний и т.д.
    """

    data_list = list(byte_string)
    k = -1
    for i in range((len(data_list) - 1) // 2):
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


async def balloon_passport_processing(nfc_tag: str, status: str):
    """
    Функция проверяет наличие и заполненность паспорта в базе данных
    """
    passport_ok_flag = False

    # проверка наличия паспорта в базе данных
    try:
        passport = await django_balloon_api.get_balloon(nfc_tag)
    except Exception as error:
        passport = None
        print(status, error)

    if passport:  # если данные паспорта есть в базе данных
        passport['status'] = status  # присваиваем новый статус баллону

        if passport['serial_number'] is None or passport['netto'] is None or passport['brutto'] is None:
            passport['update_passport_required'] = True

            # если нет основных данных - запрашиваем их в мириаде
            try:
                miriada_data = await get_balloon(nfc_tag)
            except Exception as error:
                miriada_data = None
                print('miriada error', error)

            if miriada_data:  # если получили данные из мириады
                passport['serial_number'] = miriada_data['number']
                passport['netto'] = float(miriada_data['netto'])
                passport['brutto'] = float(miriada_data['brutto'])
                passport['filling_status'] = miriada_data['status']
                passport['update_passport_required'] = False
                passport_ok_flag = True
        else:
            passport_ok_flag = True

        # обновляем паспорт в базе данных
        try:
            passport = await django_balloon_api.update_balloon(nfc_tag, passport)
        except Exception as error:
            print('update_balloon error', error)

    else:  # если данных паспорта нет в базе данных
        passport = {
            'nfc_tag': nfc_tag,
            'status': status,
            'update_passport_required': True
        }
        # создание нового паспорта в базе данных
        try:
            passport = await django_balloon_api.create_balloon(passport)
        except Exception as error:
            print('create_balloon error', error)

    return passport_ok_flag, passport


async def read_nfc_tag(reader: dict):
    """
    Асинхронная функция отправляет запрос на считыватель FEIG и получает в ответ дату, время и номер RFID метки.
    """
    data = await data_exchange_with_reader(reader, 'read_last_item_from_buffer')

    if len(data) > 24:  # если со считывателя пришли данные с меткой
        nfc_tag = byte_reversal(data[32:48])  # из буфера получаем номер метки (old - data[14:30])

        if nfc_tag not in reader['previous_nfc_tags']:  # метка отличается от недавно считанных
            try:
                balloon_passport_status, balloon_passport = await balloon_passport_processing(nfc_tag, reader['status'])

                await db.write_balloons_amount(reader, 'rfid')  # сохраняем значение в бд

                # ****************************************
                if balloon_passport_status:  # если паспорт заполнен
                    # зажигаем зелёную лампу на считывателе
                    await data_exchange_with_reader(reader, 'read_complete')
                else:
                    # мигание зелёной лампы на считывателе
                    await data_exchange_with_reader(reader, 'read_complete_with_error')
                # ****************************************

                if reader['function'] is not None:  # если производится приёмка/отгрузка баллонов
                    batch_data = await django_balloon_api.get_batch_balloons(reader['function'])

                    if batch_data:  # если партия активна - заполняем её списком пройденных баллонов
                        reader['batch']['batch_id'] = batch_data['id']
                        reader['batch']['balloon_id'] = balloon_passport['id']
                        await django_balloon_api.add_balloon_to_batch(reader)
            except Exception as error:
                print('balloon_passport_processing', error)

            # сохраняем метку в кэше считанных меток
            work_with_nfc_tag_list(nfc_tag, reader['previous_nfc_tags'])
        print(reader['ip'], reader['previous_nfc_tags'])

    # очищаем буферную память считывателя
    await data_exchange_with_reader(reader, 'clean_buffer')


async def read_input_status(reader: dict):
    """
    Функция отправляет запрос на считыватель FEIG и получает в ответ состояние дискретных входов
    """
    # присваиваем предыдущее состояние входа временной переменной
    previous_input_state = reader['input_state']

    data = await data_exchange_with_reader(reader, 'inputs_read')

    if len(data) == 18:
        print("Inputs data is: ", data)
        first_input_state = int(data[13])  # определяем состояние 1-го входа (13 индекс в ответе)
        if first_input_state == 1 and previous_input_state == 0:  # текущее состояние "активен", а ранее он был выключен
            await db.write_balloons_amount(reader, 'sensor')  # сохраняем значение в бд
            return 1  # возвращаем состояние входа "активен"
        elif first_input_state == 0 and previous_input_state == 1:
            return 0  # возвращаем состояние входа "неактивен"
        else:
            return previous_input_state
    else:
        return previous_input_state


async def main():
    # При запуске программы очищаем буфер считывателей
    tasks = [asyncio.create_task(data_exchange_with_reader(reader, 'clean_buffer')) for reader in READER_LIST]
    await asyncio.gather(*tasks)

    while True:
        try:
            # Задачи для считывания NFC тегов
            tasks = [asyncio.create_task(read_nfc_tag(reader)) for reader in READER_LIST]
            await asyncio.gather(*tasks)
        except Exception as error:
            print(f"Error while reading NFC tags: {error}")

        await asyncio.sleep(0.5)

        try:
            # Задачи для считывания состояния входов
            tasks = [asyncio.create_task(read_input_status(reader)) for reader in READER_LIST]
            results = await asyncio.gather(*tasks)

            for i in range(len(READER_LIST)):
                READER_LIST[i]['input_state'] = results[i]

        except Exception as error:
            print(f"Error while reading input status: {error}")

        await asyncio.sleep(0.5)


if __name__ == "__main__":
    asyncio.run(main())
