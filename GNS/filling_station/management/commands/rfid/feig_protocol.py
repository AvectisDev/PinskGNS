import os
import asyncio
import aiohttp
import binascii
import struct
import logging.config
import django
from typing import List, Dict, Optional
from asgiref.sync import sync_to_async
from django.conf import settings
from concurrent.futures import ThreadPoolExecutor

# Инициализация Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'GNS.settings')
django.setup()

# Конфигурация логирования из настроек Django
logging.config.dictConfig(django.conf.settings.LOGGING)
logger = logging.getLogger('rfid')

USERNAME = "reader"
PASSWORD = "rfid-device"


from filling_station.models import ReaderSettings
class Reader:
    """Класс для представления RFID-ридера"""

    def __init__(self, reader_settings: ReaderSettings):
        self.number = reader_settings.number
        self.ip = reader_settings.ip
        self.port = reader_settings.port
        self.status = reader_settings.status
        self.function = reader_settings.function
        self.need_cache = reader_settings.need_cache

        # Динамические состояния
        self.input_state = 0
        self.previous_nfc_tags = []

        # Настройки из settings.py
        from .settings import FEIG_COMMANDS
        self.commands = FEIG_COMMANDS

    def __str__(self):
        return f"Reader {self.number}: {self.ip}:{self.port} - {self.status}"

    def get_command(self, command_name: str) -> int:
        """Получение кода команды по имени"""
        return self.commands.get(command_name)


class FeigProtocol:
    """Класс для работы с протоколом FEIG"""

    STX = 0x02  # Protocol Frame Identifier

    @staticmethod
    def crc16(data: bytes) -> int:
        """
        CRC-16/CCITT-FALSE implementation for Feig protocol
        Polynomial: 0x1021 (x^16 + x^12 + x^5 + 1)
        Initial value: 0xFFFF
        """
        crc = 0xFFFF
        for byte in data:
            crc ^= byte << 8
            for _ in range(8):
                if crc & 0x8000:
                    crc = (crc << 1) ^ 0x1021
                else:
                    crc <<= 1
                crc &= 0xFFFF  # Keep only 16 bits
        return crc & 0xFFFF

    @staticmethod
    def create_request(com_adr: int, command: int, data: bytes = b'') -> bytes:
        """Создание запроса согласно протоколу FEIG"""
        # PFI + LENGTH + COM-ADR + COMMAND + DATA + CRC16
        payload = bytes([com_adr, command]) + data

        # Длина включает PFI (1) + LENGTH (2) + payload + CRC16 (2)
        length = 1 + 2 + len(payload) + 2

        # Собираем пакет
        packet = bytes([FeigProtocol.STX])  # STX
        packet += struct.pack('>H', length)  # LENGTH (big-endian)
        packet += payload  # COM-ADR + COMMAND + DATA

        # Расчет CRC16 (LSB first, MSB last)
        crc = FeigProtocol.crc16(packet)
        packet += struct.pack('<H', crc)  # CRC16 (little-endian)

        return packet

    @staticmethod
    def parse_response(response: bytes) -> Dict:
        """Парсинг ответа от ридера"""
        if len(response) < 5:
            return {'error': 'Response too short'}

        if response[0] != FeigProtocol.STX:
            return {'error': 'Invalid STX byte'}

        # Получаем длину пакета
        length = struct.unpack('>H', response[1:3])[0]

        if len(response) < length:
            return {'error': 'Incomplete response'}

        # Проверяем CRC
        packet_without_crc = response[:length - 2]
        received_crc = struct.unpack('<H', response[length - 2:length])[0]
        calculated_crc = FeigProtocol.crc16(packet_without_crc)

        if received_crc != calculated_crc:
            return {'error': 'CRC mismatch'}

        # Извлекаем данные
        com_adr = response[3]
        command = response[4]
        status = response[5]
        response_data = response[6:length - 2]

        return {
            'com_adr': com_adr,
            'command': command,
            'status': status,
            'data': response_data,
            'valid': True
        }

    @staticmethod
    def parse_buffer_data(response_data: bytes, record_layout: int) -> List[Dict]:
        """Парсинг данных из буфера (команда 0x2B)"""
        tags = []

        if len(response_data) < 6:
            return tags

        # Первые 6 байт: STATUS + DATA-SETS + RECORD-LAYOUT
        data_sets = struct.unpack('>H', response_data[2:4])[0]
        record_layout_bytes = struct.unpack('>I', response_data[4:8])[0]

        pos = 8  # Начинаем после заголовка

        for _ in range(data_sets):
            tag_data = {}

            # Проверяем наличие секции DATE
            if record_layout_bytes & (1 << 0):
                if pos + 5 <= len(response_data):
                    century, year, month, day, tz = response_data[pos:pos + 5]
                    tag_data['date'] = {
                        'century': century,
                        'year': year,
                        'month': month,
                        'day': day,
                        'tz': tz
                    }
                    pos += 5

            # Проверяем наличие секции TIME
            if record_layout_bytes & (1 << 1):
                if pos + 4 <= len(response_data):
                    hour, minute = response_data[pos:pos + 2]
                    milliseconds = struct.unpack('>H', response_data[pos + 2:pos + 4])[0]
                    tag_data['time'] = {
                        'hour': hour,
                        'minute': minute,
                        'milliseconds': milliseconds
                    }
                    pos += 4

            # Проверяем наличие секции IDD
            if record_layout_bytes & (1 << 2):
                if pos + 2 <= len(response_data):
                    transponder_type = response_data[pos]
                    idd_length = response_data[pos + 1]

                    if transponder_type == 0x03:  # ISO 15693
                        if pos + 4 + idd_length <= len(response_data):
                            afi = response_data[pos + 2]
                            dsfid = response_data[pos + 3]
                            idd_data = response_data[pos + 4:pos + 4 + idd_length]

                            # NFC Tag ID (обратный порядок байтов)
                            if idd_length >= 8:
                                # Извлекаем UID (последние 8 байт)
                                uid_bytes = idd_data[-8:] if idd_length > 8 else idd_data
                                # Конвертируем в hex строку
                                nfc_tag = binascii.hexlify(uid_bytes[::-1]).decode()
                                tag_data['nfc_tag'] = nfc_tag

                            pos += 4 + idd_length

            if 'nfc_tag' in tag_data:
                tags.append(tag_data)

        return tags


async def update_balloon(data: dict):
    """Отправка данных баллона на сервер Django"""
    async with aiohttp.ClientSession() as session:
        response = None
        try:
            async with session.post(
                    f'{settings.DJANGO_API_HOST}/balloons/update-by-reader/',
                    json=data,
                    timeout=2,
                    auth=aiohttp.BasicAuth(USERNAME, PASSWORD),
            ) as resp:
                response = resp
                logger.debug(f'Данные баллона с ридера отправлены: send_data: {data}')
                response.raise_for_status()
                return await response.json()

        except Exception as error:
            logger.error(f'Ошибка в функции отправки данных баллона с ридера: {error}, send_data: {data}')
            response_json = None
            if response is not None:
                try:
                    response_json = await response.json()
                except Exception:
                    response_json = None
            return {'error': str(error), 'response': response_json}


async def data_exchange_with_reader(reader: Reader, command_name: str, data: bytes = b'') -> Dict:
    """
    Выполняет обмен данными со считывателем FEIG.
    """
    reader_conn, writer = await asyncio.open_connection(reader.ip, reader.port)
    try:
        # Получаем код команды из настроек
        command_code = reader.get_command(command_name)
        if command_code is None:
            logger.error(f'Неизвестная команда: {command_name}')
            return {'error': f'Unknown command: {command_name}', 'valid': False}

        # Создаем запрос согласно протоколу
        # COM-ADR = 255 для не-последовательной коммуникации
        request = FeigProtocol.create_request(255, command_code, data)
        writer.write(request)
        await writer.drain()

        header = await asyncio.wait_for(reader_conn.read(5), timeout=1)
        if len(header) < 5:
            logger.error(f'Неполный заголовок от контроллера {reader.ip}')
            return {'error': 'Incomplete header', 'valid': False}

        # Получаем длину полного ответа
        length = struct.unpack('>H', header[1:3])[0]

        # Читаем оставшуюся часть пакета
        remaining = length - 5
        if remaining > 0:
            body = await asyncio.wait_for(reader_conn.read(remaining), timeout=1)
            response = header + body
        else:
            response = header

        # Парсим ответ
        parsed = FeigProtocol.parse_response(response)

        if not parsed.get('valid'):
            logger.error(f'Невалидный ответ от контроллера {reader.ip}: {parsed.get("error")}')

        return parsed

    except asyncio.TimeoutError:
        logger.error(f'Таймаут при ожидании ответа от контроллера {reader.ip}:{reader.port}')
        return {'error': 'Timeout', 'valid': False}
    except Exception as error:
        logger.error(f'Нет связи с контроллером {reader.ip}:{reader.port}: {error}')
        return {'error': str(error), 'valid': False}
    finally:
        writer.close()
        await writer.wait_closed()


def work_with_nfc_tag_list(nfc_tag: str, reader: Reader):
    """
    Функция кэширует 5 последних считанных меток и определяет, есть ли в этом списке следующая считанная метка.
    """
    if nfc_tag not in reader.previous_nfc_tags:
        if len(reader.previous_nfc_tags) > 5:
            reader.previous_nfc_tags.pop(0)
        reader.previous_nfc_tags.append(nfc_tag)
        return True
    return False


async def read_nfc_tags(reader: Reader):
    """
    Чтение всех меток из буфера ридера. Возвращает список уникальных меток.
    """
    # MODE = 0x00, DATA-SETS = 0xFFFF (читать все доступные)
    request_data = b'\x00' + b'\xFF\xFF'  # MODE + DATA-SETS

    response = await data_exchange_with_reader(reader, 'READ_BUFFER', request_data)

    tags = []
    if response.get('valid') and response.get('status') == 0:
        # Парсим данные буфера
        tags_data = FeigProtocol.parse_buffer_data(response['data'], 0)

        for tag_data in tags_data:
            if 'nfc_tag' in tag_data:
                nfc_tag = tag_data['nfc_tag'].upper()

                # Проверяем уникальность и добавляем в кэш при необходимости
                if work_with_nfc_tag_list(nfc_tag, reader):
                    tags.append(nfc_tag)

    return tags


async def read_input_status(reader: Reader) -> int:
    """
    Чтение состояния входов ридера (команда GET_INPUT). Возвращает состояние первого входа (IN1).
    """
    response = await data_exchange_with_reader(reader, 'GET_INPUT')

    if response.get('valid') and response.get('status') == 0 and len(response.get('data', [])) >= 1:
        inputs_byte = response['data'][0]  # Байт состояния входов
        # IN1 находится в бите 0
        input_state = (inputs_byte >> 0) & 0x01
        return input_state

    return reader.input_state  # Возвращаем предыдущее состояние при ошибке


async def process_reader_operations(reader: Reader):
    """
    Основная функция обработки операций ридера.
    """
    while True:
        try:
            # 1. Проверяем состояние входов
            current_input_state = await read_input_status(reader)

            # Если состояние изменилось с 0 на 1 (передний фронт)
            if current_input_state == 1 and reader.input_state == 0:
                post_data = {
                    'nfc_tag': None,
                    'reader_number': reader.number
                }
                await update_balloon(post_data)
                logger.info(f'Сработал вход на ридере {reader.ip}')

            # Обновляем состояние входа
            reader.input_state = current_input_state

            # 2. Читаем метки из буфера
            tags = await read_nfc_tags(reader)

            for nfc_tag in tags:
                try:
                    post_data = {
                        'nfc_tag': nfc_tag,
                        'reader_number': reader.number
                    }

                    balloon_passport = await update_balloon(post_data)

                    # Управление светодиодами ридера
                    if balloon_passport.get('filling_status') == True:
                        # Зажигаем зелёную лампу
                        await data_exchange_with_reader(reader, 'SET_OUTPUT', b'\x01\x01\x81\x01\x00')
                    else:
                        # Мигание зелёной лампы
                        await data_exchange_with_reader(reader, 'SET_OUTPUT', b'\x01\x01\x81\x0B\x00')

                except Exception as error:
                    logger.error(f'Ошибка обработки метки {nfc_tag} на ридере {reader.ip}: {error}')

            # 3. Очищаем буфер (только прочитанные записи)
            if tags:
                await data_exchange_with_reader(reader, 'CLEAR_BUFFER')

            # Небольшая задержка перед следующей итерацией
            await asyncio.sleep(0.1)

        except Exception as error:
            logger.error(f"Ошибка в process_reader_operations для ридера {reader.ip}: {error}")
            await asyncio.sleep(1)  # Пауза при ошибке


async def initialize_readers(readers: List[Reader]):
    """
    Инициализация ридеров при запуске.
    """
    tasks = []
    for reader in readers:
        # Очищаем буфер при запуске
        task = asyncio.create_task(data_exchange_with_reader(reader, 'INITIALIZE_BUFFER'))
        tasks.append(task)

    logger.info('Инициализация RFID-считывателей...')
    await asyncio.gather(*tasks)

    # Считываем начальное состояние входов
    for reader in readers:
        reader.input_state = await read_input_status(reader)


def process_reader_sync(reader: Reader):
    """Синхронная обертка для запуска в ThreadPoolExecutor"""
    asyncio.run(process_reader_operations(reader))


async def load_readers_from_database():
    """
    Загрузка конфигурации ридеров из базы данных Django.
    """
    readers = []

    @sync_to_async
    def get_readers_from_db():
        return list(ReaderSettings.objects.all().order_by('number'))

    try:
        reader_settings_list = await get_readers_from_db()

        for reader_settings in reader_settings_list:
            # Проверяем, что у ридера есть IP адрес
            if reader_settings.ip:
                reader = Reader(reader_settings)
                readers.append(reader)
                logger.info(f'Загружен ридер {reader}')
            else:
                logger.warning(f'Ридер {reader_settings.number} не имеет IP адреса, пропускаем')

    except Exception as error:
        logger.error(f'Ошибка при загрузке ридеров из базы данных: {error}')

    return readers


async def main():
    logger.info('Запуск программы считывания RFID-меток с использованием протокола FEIG...')

    # Загрузка ридеров из базы данных
    readers = await load_readers_from_database()

    if not readers:
        logger.error('Не удалось загрузить конфигурацию ридеров. Завершение работы.')
        return

    # Инициализация ридеров
    await initialize_readers(readers)

    # Запуск обработки для каждого ридера
    with ThreadPoolExecutor(max_workers=len(readers)) as executor:
        logger.info('Программа в работе')
        loop = asyncio.get_running_loop()
        tasks = [
            loop.run_in_executor(executor, process_reader_sync, reader)
            for reader in readers
        ]
        await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
