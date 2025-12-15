import os
import asyncio
import aiohttp
import binascii
import struct
import logging.config
import django
from typing import List, Dict
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

    def __str__(self):
        return f"Reader {self.number}: {self.ip}:{self.port} - {self.status}"


class FeigProtocol:
    """Класс для работы с протоколом FEIG"""
    # Константы класса
    FEIG_COMMANDS = {
        'GET_INPUT': 0x74,  # Чтение состояния входов
        'SET_OUTPUT': 0x72,  # Управление выходами/LED
        'READ_BUFFER': 0x2B,  # Чтение буфера
        'CLEAR_BUFFER': 0x32,  # Очистка прочитанных
        'INITIALIZE_BUFFER': 0x33,  # Полная очистка буфера
    }

    STATUS_BYTE = {
        0x00: 'OK:',
        0x01: 'No Transponder:',
        0x02: 'Data False:',
        0x03: 'Write Error:',
        0x04: 'Address Error:',
        0x05: 'Wrong Transponder Type:',
        0x0F: 'Busy',
        0x10: 'EEPROM Failure:',
        0x11: 'Parameter Range Error',
        0x13: 'Login Request',
        0x14: 'Login Error',
        0x15: 'Read Protect',
        0x16: 'Write Protect',
        0x17: 'Firmware Activation Required',
        0x80: 'Unknown Command',
        0x81: 'Length Error',
        0x82: 'Command Not Available',
        0x83: 'RF Communication Error',
        0x84: 'RF Warning',
        0x92: 'No Valid Data',
        0x93: 'Data Buffer Overflow',
        0x94: 'More Data',
        0x95: 'Tag Error',
        0xF1: 'Hardware Warning',
        0xF2: 'Initialization Warning',
        0x20: 'External Device error',
    }

    STX = 0x02  # Protocol Frame Identifier

    @staticmethod
    def crc16(data: bytes) -> int:
        """
        CRC-16 для FEIG (LSB-first):
        """
        crc = 0xFFFF
        for byte in data:
            crc ^= byte
            for _ in range(8):
                if crc & 0x0001:
                    crc = (crc >> 1) ^ 0x8408
                else:
                    crc >>= 1
            crc &= 0xFFFF
        return crc & 0xFFFF

    @classmethod
    def get_command(cls, name: str) -> int:
        """Возвращает числовой код команды по имени или ошибку."""
        try:
            return cls.FEIG_COMMANDS[name]
        except KeyError:
            raise ValueError(f"Unknown FEIG command name: {name!r}")

    @classmethod
    def create_request(cls, command_name: str, data_sets: bytes = b'') -> bytes:
        """
        Создание запроса согласно протоколу FEIG
        REQUEST PROTOCOL (Host): STX + LENGTH + COM-ADR + COMMAND + REQUEST-DATA + CRC16
        LENGTH and CRC16 in MSB/LSB (BIG-ENDIAN) mode
        """
        com_adr = 0xFF  # Используется протокол TCP/IP
        command = cls.get_command(command_name)

        # Длина включает STX (1) + LENGTH (2) + COM-ADR(1) + payload + CRC16 (2)
        length = 1 + 2 + 1 + 1 + len(data_sets) + 2

        # Собираем пакет
        packet = bytes([FeigProtocol.STX])
        packet += struct.pack('>H', length)  # LENGTH (big-endian)
        packet += bytes([com_adr, command])
        packet += data_sets

        # Расчет CRC16 (LSB first, MSB last)
        crc = FeigProtocol.crc16(packet)
        packet += struct.pack('<H', crc)  # CRC16 (little-endian)

        return packet

    @staticmethod
    def parse_response(response: bytes) -> Dict:
        """Парсинг ответа от ридера"""
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
        response_data = response[4:length - 2]

        return {
            'com_adr': com_adr,
            'response_data': response_data,
            'valid': True
        }

    @staticmethod
    def parse_buffer_data(response_data: bytes) -> List[Dict]:
        """Парсинг данных из буфера (команда 0x2B)"""
        tags = []

        command = response_data[0]
        status = response_data[1]
        # Сохраняем статус ответа
        tags.append({'status': FeigProtocol.STATUS_BYTE[status]})

        # Если в буфере нет данных - завершаем обработку
        if status == 0x92:
            return tags

        match command:
            case 0x2B:  # READ_BUFFER
                data_sets = struct.unpack('>H', response_data[2:4])[0]

                pos = 4  # Начинаем после заголовка

                for _ in range(data_sets):
                    tag_data = {}

                    record_layout_bits = struct.unpack('>I', response_data[pos:pos + 4])[0]
                    pos += 4
                    # Проверяем наличие секции DATE
                    if record_layout_bits & (1 << 0):
                        century, year, month, day, tz = response_data[pos:pos + 5]
                        tag_data.update({
                            'century': century,
                            'year': year,
                            'month': month,
                            'day': day,
                            'tz': tz
                        })
                        pos += 5

                    # Проверяем наличие секции TIME
                    if record_layout_bits & (1 << 1):
                        hour, minute = response_data[pos:pos + 2]
                        milliseconds = struct.unpack('>H', response_data[pos + 2:pos + 4])[0]
                        tag_data.update({
                            'hour': hour,
                            'minute': minute,
                            'milliseconds': milliseconds
                        })
                        pos += 4

                    # Проверяем наличие секции IDD
                    if record_layout_bits & (1 << 2):
                        transponder_type = response_data[pos]
                        if transponder_type == 0x03:  # ISO 15693
                            afi = response_data[pos + 1]
                            dsfid = response_data[pos + 2]
                            idd_length = response_data[pos + 3]
                            idd_data = response_data[pos + 4:pos + 4 + idd_length]

                            # Конвертируем NFC Tag ID в hex строку (обратный порядок байтов)
                            nfc_tag = binascii.hexlify(idd_data[::-1]).decode()
                            tag_data.update({
                                'transponder_type': transponder_type,
                                'afi': afi,
                                'dsfid': dsfid,
                                'nfc_tag': nfc_tag,
                            })

                            # Пропускаем обработку ненужных данных в пакете
                            pos += 4 + idd_length
                            pos += 2  # inputs state (2 byte)
                            pos += 4  # signals (4 byte)

                    if 'nfc_tag' in tag_data:
                        tags.append(tag_data)

                return tags

            case _:
                tags.append({'error': f'Unsupported command: {command}'})
                logger.error(f'Неизвестная команда: {command}')
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


async def data_exchange_with_reader(reader: Reader, command_name: str, request_data: bytes = b'') -> Dict:
    """
    Выполняет обмен данными со считывателем FEIG.
    """
    reader_conn, writer = await asyncio.open_connection(reader.ip, reader.port)
    try:
        # Создаем запрос согласно протоколу
        request = FeigProtocol.create_request(command_name, request_data)
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
    if response.get('valid'):
        # Парсим данные буфера
        tags_data = FeigProtocol.parse_buffer_data(response.get('response_data'))

        for tag_data in tags_data:
            if 'nfc_tag' in tag_data:
                nfc_tag = tag_data['nfc_tag']

                # Проверяем уникальность и добавляем в кэш при необходимости
                if work_with_nfc_tag_list(nfc_tag, reader):
                    tags.append(nfc_tag)

    return tags


async def read_input_status(reader: Reader) -> int:
    """
    Чтение состояния входов ридера (команда GET_INPUT). Возвращает состояние первого входа (IN1).
    """
    response = await data_exchange_with_reader(reader, 'GET_INPUT')

    if response.get('valid'):
        inputs_byte = response.get('response_data')[0]  # Байт состояния входов
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
            await asyncio.sleep(0.3)

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
        return list(ReaderSettings.objects.all())

    try:
        reader_settings_list = await get_readers_from_db()

        for reader_settings in reader_settings_list:
            reader = Reader(reader_settings)
            readers.append(reader)
            logger.info(f'Загружен ридер {reader}')

    except Exception as error:
        logger.error(f'Ошибка при загрузке ридеров из базы данных: {error}')

    return readers


async def main():
    logger.info('Запуск программы считывания RFID-меток...')

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
