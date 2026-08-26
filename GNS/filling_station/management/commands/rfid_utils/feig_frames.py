"""Сборка и разбор кадров протокола FEIG (Advanced Protocol Frame)."""

import struct
import binascii
from typing import List, Dict
import logging
logger = logging.getLogger('rfid')


class FeigProtocol:
    """Кодирование запросов и парсинг ответов/событий FEIG."""

    # Команды протокола
    FEIG_COMMANDS = {
        'GET_INPUT': 0x74,           # чтение состояния входов
        'SET_OUTPUT': 0x72,          # управление выходами/LED
        'READ_BUFFER': 0x2B,         # чтение буфера (data sets)
        'READ_BUFFER_INFO': 0x31,    # информация о буфере (наличие записей)
        'CLEAR_BUFFER': 0x32,        # очистка прочитанных записей
        'INITIALIZE_BUFFER': 0x33,   # полная очистка буфера
        'READER_IDENTIFICATION_EVENT': 0x2A,  # Notification Mode: hello/heartbeat
        'TAG_READ_EVENT': 0x2B,      # Notification Mode: event with tag data
        'INPUT_EVENT': 0x2C,         # Notification Mode: digital input change
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
        CRC-16 для FEIG (LSB-first, полином 0x8408).

        Args:
            data (bytes): Байты кадра без поля CRC.

        Returns:
            int: Значение CRC-16 (0..0xFFFF).
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
        """
        Возвращает числовой код команды по имени.

        Args:
            name (str): Ключ из ``FEIG_COMMANDS``.

        Returns:
            int: Код команды FEIG.

        Raises:
            ValueError: Если имя команды неизвестно.
        """
        try:
            return cls.FEIG_COMMANDS[name]
        except KeyError:
            raise ValueError(f"Unknown FEIG command name: {name!r}")

    @classmethod
    def create_request(cls, command_name: str, request_data: bytes = b'') -> bytes:
        """
        Создаёт Advanced Protocol Frame запрос по имени команды.

        Формат: STX + ALENGTH(2) + COM-ADR(1) + COMMAND(1) + DATA + CRC16(LSB,MSB).
        ALENGTH — big-endian; CRC — little-endian.

        Args:
            command_name (str): Имя команды из ``FEIG_COMMANDS``.
            request_data (bytes): Поле DATA (по умолчанию пустое).

        Returns:
            bytes: Готовый кадр для отправки на ридер.
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
    def create_request_by_code(cls, command_code: int, request_data: bytes = b'') -> bytes:
        """
        Создаёт запрос по числовому коду команды.

        Используется для ACK Notification Mode events (0x2A/0x2B/0x2C).

        Args:
            command_code (int): Код команды FEIG.
            request_data (bytes): Поле DATA (для ACK обычно 1 байт статуса).

        Returns:
            bytes: Готовый кадр для отправки на ридер.
        """
        com_adr = 0xFF
        length = 1 + 2 + 1 + 1 + len(request_data) + 2

        packet = bytes([FeigProtocol.STX])
        packet += struct.pack('>H', length)
        packet += bytes([com_adr, command_code & 0xFF])
        packet += request_data

        crc = FeigProtocol.crc16(packet)
        packet += struct.pack('<H', crc)
        return packet

    @classmethod
    def parse_response(cls, response: bytes) -> Dict:
        """
        Разбирает ответ ридера с проверкой длины и CRC.

        Args:
            response (bytes): Полный кадр ответа.

        Returns:
            dict: При успехе — ``com_adr``, ``response_data``, ``valid=True``;
                при ошибке — ``error``, ``valid=False``.
        """
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
        Парсит payload ответа/события: буфер (0x2B, 0x31), входы (0x74), Notification (0x2A/0x2C).

        Первый элемент списка всегда содержит ``command`` и ``status``;
        последующие — разобранные записи (метки, состояния входов и т.д.).

        Args:
            response_data (bytes): Поле DATA кадра без заголовка STX/ALENGTH/CRC.

        Returns:
            list[dict]: Список записей; пустой список при слишком коротком payload.
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

            case 0x2A:  # READER_IDENTIFICATION / HEARTBEAT EVENT
                # Для текущей логики нам достаточно command/status + сырой payload.
                tags.append({'raw_event_payload': response_data[2:]})
                return tags

            case 0x2C:  # INPUT EVENT
                if len(response_data) < 8:
                    logger.warning(f'Недостаточно данных для INPUT_EVENT: {len(response_data)} байт')
                    return tags

                data_sets = struct.unpack('>H', response_data[2:4])[0]
                record_layout_bits = struct.unpack('>I', response_data[4:8])[0]
                pos = 8

                logger.debug(
                    f'INPUT_EVENT header: data_sets={data_sets}, record_layout=0x{record_layout_bits:08X}, '
                    f'payload_len={len(response_data)}'
                )

                # Input sector в RECORD-LAYOUT:
                # - в разделе Input Event (0x2C) в мануале указан бит 2;
                # - на практике LRM5400 шлёт тот же bitfield, что и для Tag Read Event (0x2B),
                #   где INPUT — бит 12 (0x00001000).
                has_input_sector = bool(record_layout_bits & (1 << 2)) or bool(
                    record_layout_bits & (1 << 12)
                )
                if not has_input_sector:
                    logger.warning(
                        f'INPUT_EVENT без input-сектора в layout (0x{record_layout_bits:08X}); '
                        f'ожидались биты 2 или 12'
                    )
                    return tags

                for _ in range(data_sets):
                    if len(response_data) < pos + 8:
                        logger.warning(
                            f'Недостаточно данных для INPUT_EVENT record. Позиция: {pos}, длина: {len(response_data)}'
                        )
                        break

                    previous_state = struct.unpack('>I', response_data[pos:pos + 4])[0]
                    current_state = struct.unpack('>I', response_data[pos + 4:pos + 8])[0]
                    pos += 8

                    tags.append({
                        'previous_state': previous_state,
                        'current_state': current_state,
                        'IN1_previous': bool(previous_state & (1 << 0)),
                        'IN1_current': bool(current_state & (1 << 0)),
                        'IN2_previous': bool(previous_state & (1 << 1)),
                        'IN2_current': bool(current_state & (1 << 1)),
                        'IN3_previous': bool(previous_state & (1 << 2)),
                        'IN3_current': bool(current_state & (1 << 2)),
                    })
                return tags

            case _:  # UNKNOWN
                logger.error(f'Неизвестная команда: 0x{command:02X} ({command}) в ответе от ридера')
                # Возвращаем только информацию о команде и статусе, без попытки парсинга
                return tags

