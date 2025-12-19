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

    @classmethod
    def parse_response(cls, response: bytes) -> Dict:
        """Парсинг ответа от ридера"""
        if response[0] != cls.STX:
            return {'error': 'Invalid STX byte'}

        # Получаем длину пакета
        length = struct.unpack('>H', response[1:3])[0]

        if len(response) < length:
            return {'error': f'Неверная длина {bytes(response).hex()}'}

        # Проверяем CRC
        packet_without_crc = response[:length - 2]
        received_crc = struct.unpack('<H', response[length - 2:length])[0]
        calculated_crc = cls.crc16(packet_without_crc)

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

    @classmethod
    def parse_buffer_data(cls, response_data: bytes) -> List[Dict]:
        """Парсинг данных из буфера (команда 0x2B)"""
        tags = []

        command = response_data[0]
        status = response_data[1]
        # Сохраняем статус ответа
        tags.append({
            'command': bytes(command).hex(),
            'status': cls.STATUS_BYTE.get(status, "Unknown"),
            })

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

            case 0x74:  # GET_INPUT
                inputs_byte = response_data[2]
                input_state = {
                    'IN1': bool(inputs_byte & (1 << 0)),
                    'IN2': bool(inputs_byte & (1 << 1)),
                    'IN3': bool(inputs_byte & (1 << 2)),
                }

                tags.append(input_state)
                return tags

            case _:  # UNKNOWN
                logger.error(f'Неизвестная команда: {command}')
                return tags
