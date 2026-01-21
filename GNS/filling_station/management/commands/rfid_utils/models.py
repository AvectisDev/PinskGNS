import asyncio
import struct
import binascii
from collections import deque
from typing import List, Dict
import logging
logger = logging.getLogger('rfid')


class Reader:
    """Класс для представления RFID-ридера"""
    def __init__(self, reader_settings):
        self.number = reader_settings.number
        self.ip = reader_settings.ip
        self.port = reader_settings.port
        self.status = reader_settings.status
        self.function = reader_settings.function
        self.need_cache = reader_settings.need_cache
        # Динамические состояния
        self.input_state = 0
        self.previous_nfc_tags = deque(maxlen=5)  # кеш последних меток

    def __str__(self):
        return f"Reader {self.number}: {self.ip}:{self.port} - {self.status}"

    def filter_duplicate_tag(self, nfc_tag: str) -> bool:
        """
        Кэширует 5 последних считанных меток и определяет, есть ли в этом списке следующая считанная метка.
        Возвращает True если метка новая (ещё не была в последних 5)
        """
        if nfc_tag in self.previous_nfc_tags:
            return False
        self.previous_nfc_tags.append(nfc_tag)
        return True


class FeigProtocol:
    """Класс для работы с протоколом FEIG"""
    # Команды протокола
    FEIG_COMMANDS = {
        'GET_INPUT': 0x74,           # чтение состояния входов
        'SET_OUTPUT': 0x72,          # управление выходами/LED
        'READ_BUFFER': 0x2B,         # чтение буфера (data sets)
        'READ_BUFFER_INFO': 0x31,    # информация о буфере (наличие записей)
        'CLEAR_BUFFER': 0x32,        # очистка прочитанных записей
        'INITIALIZE_BUFFER': 0x33,   # полная очистка буфера
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
        CRC-16 для FEIG (LSB-first, полином 0x8408)
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
    def create_request(cls, command_name: str, request_data: bytes = b'') -> bytes:
        """
        Создание запроса согласно протоколу FEIG
        Advanced frame: STX + ALENGTH(2) + COM-ADR(1) + COMMAND(1) + DATA + CRC16(LSB,MSB)
        ALENGTH и CRC16 кодируются в MSB/LSB (big-endian для длины; CRC упаковываем little-endian).
        """
        com_adr = 0xFF  # при TCP/IP обычно используется широковещательный адрес шины
        command = cls.get_command(command_name)
        # Общая длина кадра: STX(1) + ALENGTH(2) + COM(1) + CMD(1) + data + CRC(2)
        length = 1 + 2 + 1 + 1 + len(request_data) + 2

        packet = bytes([FeigProtocol.STX])
        packet += struct.pack('>H', length)      # ALENGTH
        packet += bytes([com_adr, command])
        packet += request_data

        crc = FeigProtocol.crc16(packet)         # CRC над всем кадром, кроме самого CRC
        packet += struct.pack('<H', crc)         # CRC16: LSB first
        return packet

    @classmethod
    def parse_response(cls, response: bytes) -> Dict:
        """Парсинг ответа от ридера с проверкой длины и CRC."""
        if not response or response[0] != cls.STX:
            return {'error': 'Invalid STX byte', 'valid': False}

        length = struct.unpack('>H', response[1:3])[0]
        if len(response) < length:
            return {'error': f'Неверная длина {bytes(response).hex()}', 'valid': False}

        packet_without_crc = response[:length - 2]
        received_crc = struct.unpack('<H', response[length - 2:length])[0]
        calculated_crc = cls.crc16(packet_without_crc)
        if received_crc != calculated_crc:
            return {'error': 'CRC mismatch', 'valid': False}

        com_adr = response[3]
        response_data = response[4:length - 2]
        return {
            'com_adr': com_adr,
            'response_data': response_data,
            'valid': True
        }

    @classmethod
    def parse_buffer_data(cls, response_data: bytes) -> List[Dict]:
        """
        Парсинг данных из буфера (команды 0x2B, 0x31) и входов (0x74)
        """
        tags = []
        
        # Проверка минимальной длины ответа
        if len(response_data) < 2:
            logger.error(f'Недостаточно данных в ответе: {len(response_data)} байт')
            return tags
        
        command = response_data[0]
        status = response_data[1]

        # сохраняем статус ответа
        tags.append({
            'command': command,
            'status': cls.STATUS_BYTE.get(status, f"Unknown status: 0x{status:02X}"),
        })

        # Проверяем статус на ошибки перед парсингом
        if status != 0x00:  # 0x00 = OK
            error_msg = cls.STATUS_BYTE.get(status, f"Unknown status: 0x{status:02X}")
            logger.warning(f'Статус ответа указывает на проблему: {error_msg} (0x{status:02X})')
            # Нет валидных данных или другая ошибка - возвращаем только статус
            if status == 0x92:  # No Valid Data
                return tags
            # Для других ошибок также возвращаем только статус, чтобы избежать парсинга некорректных данных
            return tags

        match command:
            case 0x2B:  # READ_BUFFER
                if len(response_data) < 4:
                    logger.warning(f'Недостаточно данных для READ_BUFFER: {len(response_data)} байт')
                    return tags
                data_sets = struct.unpack('>H', response_data[2:4])[0]
                pos = 4  # начало записей

                for _ in range(data_sets):
                    # Проверяем, что у нас достаточно данных для чтения record_layout_bits
                    if len(response_data) < pos + 4:
                        logger.warning(f'Недостаточно данных для чтения record_layout_bits. Позиция: {pos}, длина данных: {len(response_data)}')
                        break
                    tag_data = {}
                    record_layout_bits = struct.unpack('>I', response_data[pos:pos + 4])[0]
                    pos += 4

                    # DATE
                    if record_layout_bits & (1 << 0):
                        if len(response_data) < pos + 5:
                            logger.warning(f'Недостаточно данных для DATE. Позиция: {pos}, длина данных: {len(response_data)}')
                            break
                        century, year, month, day, tz = response_data[pos:pos + 5]
                        tag_data.update({
                            'century': century,
                            'year': year,
                            'month': month,
                            'day': day,
                            'tz': tz
                        })
                        pos += 5

                    # TIME
                    if record_layout_bits & (1 << 1):
                        if len(response_data) < pos + 4:
                            logger.warning(f'Недостаточно данных для TIME. Позиция: {pos}, длина данных: {len(response_data)}')
                            break
                        hour, minute = response_data[pos:pos + 2]
                        milliseconds = struct.unpack('>H', response_data[pos + 2:pos + 4])[0]
                        tag_data.update({
                            'hour': hour,
                            'minute': minute,
                            'milliseconds': milliseconds
                        })
                        pos += 4

                    # IDD (ISO15693)
                    if record_layout_bits & (1 << 2):
                        if len(response_data) < pos + 1:
                            logger.warning(f'Недостаточно данных для IDD. Позиция: {pos}, длина данных: {len(response_data)}')
                            break
                        transponder_type = response_data[pos]
                        match transponder_type:
                            case 0x00: # I-CODE1 (TR-TYPE = 0x00)
                                if len(response_data) < pos + 3:
                                    logger.warning(f'Недостаточно данных для I-CODE1. Позиция: {pos}, длина данных: {len(response_data)}')
                                    break
                                idd_length = response_data[pos + 1]
                                if len(response_data) < pos + 2 + idd_length:
                                    logger.warning(f'Недостаточно данных для I-CODE1 IDD. Позиция: {pos}, длина: {idd_length}, доступно: {len(response_data) - pos - 2}')
                                    break
                                idd_data = response_data[pos + 2:pos + 2 + idd_length]
                                # NFC Tag ID в обратном порядке байтов -> hex
                                nfc_tag = binascii.hexlify(idd_data[::-1]).decode()
                                tag_data.update({
                                    'transponder_type': transponder_type,
                                    'nfc_tag': nfc_tag,
                                })
                                pos += 2 + idd_length
                            case 0x03: # ISO 15693 (TR-TYPE = 0x03)
                                if len(response_data) < pos + 5:
                                    logger.warning(f'Недостаточно данных для ISO 15693. Позиция: {pos}, длина данных: {len(response_data)}')
                                    break
                                afi = response_data[pos + 1]
                                dsfid = response_data[pos + 2]
                                idd_length = response_data[pos + 3]
                                if len(response_data) < pos + 4 + idd_length:
                                    logger.warning(f'Недостаточно данных для ISO 15693 IDD. Позиция: {pos}, длина: {idd_length}, доступно: {len(response_data) - pos - 4}')
                                    break
                                idd_data = response_data[pos + 4:pos + 4 + idd_length]
                                # NFC Tag ID в обратном порядке байтов -> hex
                                nfc_tag = binascii.hexlify(idd_data[::-1]).decode()
                                tag_data.update({
                                    'transponder_type': transponder_type,
                                    'afi': afi,
                                    'dsfid': dsfid,
                                    'nfc_tag': nfc_tag,
                                })
                                pos += 4 + idd_length
                            case 0x09:  # ISO 18000-3M3 (TR-TYPE = 0x09)
                                if len(response_data) < pos + 4:
                                    logger.warning(f'Недостаточно данных для ISO 18000-3M3. Позиция: {pos}, длина данных: {len(response_data)}')
                                    break
                                iddt = response_data[pos + 1]
                                idd_length = response_data[pos + 2]
                                if len(response_data) < pos + 3 + idd_length:
                                    logger.warning(f'Недостаточно данных для ISO 18000-3M3 IDD. Позиция: {pos}, длина: {idd_length}, доступно: {len(response_data) - pos - 3}')
                                    break
                                idd_data = response_data[pos + 3:pos + 3 + idd_length]
                                # NFC Tag ID в обратном порядке байтов -> hex
                                nfc_tag = binascii.hexlify(idd_data[::-1]).decode()
                                tag_data.update({
                                    'transponder_type': transponder_type,
                                    'iddt': iddt,
                                    'nfc_tag': nfc_tag,
                                })
                                pos += 3 + idd_length
                            case _:
                                logger.warning(f'Неизвестный тип транспондера: 0x{transponder_type:02X}')
                                # Пропускаем эту запись, так как не знаем структуру данных
                                break

                        # inputs state (2 byte) и signals (4 byte) - только если IDD был успешно обработан
                        if 'nfc_tag' in tag_data:
                            if len(response_data) < pos + 6:
                                logger.warning(f'Недостаточно данных для inputs/signals. Позиция: {pos}, длина данных: {len(response_data)}')
                                break
                            pos += 2  # inputs state (2 byte)
                            pos += 4  # signals (4 byte)

                    if 'nfc_tag' in tag_data:
                        tags.append(tag_data)
                logger.debug(f'Распаршены метки: {tags}')
                return tags

            case 0x31:  # READ_BUFFER_INFO
                # Минимально необходимое: первые 2 байта после статуса трактуем
                # как число доступных записей (DATA-SETS/AVAILABLE)
                if len(response_data) < 4:
                    logger.warning(f'Недостаточно данных для READ_BUFFER_INFO: {len(response_data)} байт')
                    return tags
                available = struct.unpack('>H', response_data[2:4])[0]
                tags.append({'available': available})
                return tags

            case 0x74:  # GET_INPUT
                if len(response_data) < 3:
                    logger.warning(f'Недостаточно данных для GET_INPUT: {len(response_data)} байт')
                    return tags
                inputs_byte = response_data[2]
                input_state = {
                    'IN1': bool(inputs_byte & (1 << 0)),
                    'IN2': bool(inputs_byte & (1 << 1)),
                    'IN3': bool(inputs_byte & (1 << 2)),
                }
                tags.append(input_state)
                return tags

            case 0x32:  # CLEAR_BUFFER
                # Команда очистки буфера - возвращает только статус
                logger.debug('CLEAR_BUFFER выполнен')
                return tags

            case 0x33:  # INITIALIZE_BUFFER
                # Команда полной инициализации буфера - возвращает только статус
                logger.debug('INITIALIZE_BUFFER выполнен')
                return tags

            case _:  # UNKNOWN
                logger.error(f'Неизвестная команда: 0x{command:02X} ({command}) в ответе от ридера')
                # Возвращаем только информацию о команде и статусе, без попытки парсинга
                return tags


class ReaderSession:
    """
    Постоянная TCP-сессия к ридеру FEIG.
    Обеспечивает последовательную отправку команд и точное чтение ответа по длине (ALENGTH).
    """
    def __init__(self, reader: Reader):
        self.reader = reader
        self.conn = None
        self.writer = None
        self.lock = None  # создаётся при подключении

    async def connect(self):
        if self.conn is None or self.writer is None:
            self.conn, self.writer = await asyncio.open_connection(self.reader.ip, self.reader.port)
            self.lock = asyncio.Lock()
            logger.info(f'{self.reader} TCP connected')

    async def close(self):
        if self.writer:
            try:
                self.writer.close()
                await self.writer.wait_closed()
            finally:
                self.conn = None
                self.writer = None
                self.lock = None
                logger.info(f'{self.reader} TCP closed')

    async def send(self, command_name: str, request_data: bytes = b'') -> Dict:
        """
        Последовательная отправка команды с корректным чтением полного кадра ответа.
        """
        if self.conn is None or self.writer is None:
            await self.connect()

        async with self.lock:
            req = FeigProtocol.create_request(command_name, request_data)
            logger.debug(f'{self.reader.number} Отправляем запрос: {req.hex()}, Команда {command_name}')
            self.writer.write(req)
            await self.writer.drain()

            # читаем заголовок (5 байт): STX(1) + ALENGTH(2) + COM-ADR(1) + COMMAND(1)
            try:
                header = await asyncio.wait_for(self.conn.read(5), timeout=1.0)
                if len(header) < 5 or header[0] != FeigProtocol.STX:
                    return {'valid': False, 'error': 'Incomplete/invalid header'}

                length = struct.unpack('>H', header[1:3])[0]  # ALENGTH
                remaining = length - 5
                body = b''
                if remaining > 0:
                    body = await asyncio.wait_for(self.conn.read(remaining), timeout=1.0)

                response = header + body
                logger.debug(f'{self.reader.number} Ответ ридера: {response.hex()}, Команда {command_name}')
                return FeigProtocol.parse_response(response)

            except asyncio.TimeoutError:
                return {'valid': False, 'error': 'Timeout'}
            except Exception as e:
                return {'valid': False, 'error': str(e)}
