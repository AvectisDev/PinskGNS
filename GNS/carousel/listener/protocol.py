"""
Бинарный протокол обмена с постами наполнения (8 байт, CRC-16/AUG-CCITT).

Формат кадра (big-endian):
    [0] тип запроса/ответа
    [1] номер поста
    [2] служебный байт
    [3:5] вес, граммы (uint16)
    [5] флаг наполнения
    [6:8] CRC первых шести байт

Типы запросов от поста:
    0x7A — запрос наполнения (пустой баллон на весах)
    0x70 — фиксация полного веса

Типы ответов сервера:
    0x5A — целевой полный вес для 0x7A
    0x50 — подтверждение для 0x70
"""

import struct
from dataclasses import dataclass

from .config import FRAME_SIZE

REQUEST_TYPE_FILL = 0x7A
RESPONSE_TYPE_FILL = 0x5A
REQUEST_TYPE_FULL_WEIGHT = 0x70
RESPONSE_TYPE_FULL_WEIGHT = 0x50

REQUEST_TYPE_FILL_STR = '0x7a'
REQUEST_TYPE_FULL_WEIGHT_STR = '0x70'


@dataclass(frozen=True)
class FrameFields:
    """Распарсенные поля входящего 8-байтного кадра от поста."""

    request_type: int
    request_type_str: str
    post_number: int
    service_byte: int
    weight_combined: int
    fill_flag: int


def parse_request_frame(data: bytes) -> FrameFields:
    """
    Разбирает принятый кадр фиксированной длины.

    Args:
        data: Ровно FRAME_SIZE байт.

    Returns:
        Поля кадра для дальнейшей обработки.
    """
    request_type = data[0]
    return FrameFields(
        request_type=request_type,
        request_type_str=hex(request_type),
        post_number=data[1],
        service_byte=data[2],
        weight_combined=(data[3] << 8) | data[4],
        fill_flag=data[5],
    )


def calc_crc(message: bytes) -> int:
    """Вычисляет CRC-16/AUG-CCITT (алгоритм контроллера поста)."""
    poly = 0x1021
    reg = 0xFFFF
    message += b'\x00\x00'
    for byte in message:
        mask = 0x80
        while mask > 0:
            reg <<= 1
            if byte & mask:
                reg += 1
            mask >>= 1
            if reg > 0xffff:
                reg &= 0xffff
                reg ^= poly
    return reg


def validate_frame_crc(frame: bytes) -> tuple[bool, int, int]:
    """
    Проверяет CRC16/SPI-FUJITSU первых шести байт кадра.

    Returns:
        Кортеж (валиден, полученный CRC, рассчитанный CRC).
    """
    if len(frame) != FRAME_SIZE:
        return False, 0, 0
    received_crc = int.from_bytes(frame[6:8], byteorder='big')
    calculated_crc = calc_crc(frame[:6])
    return received_crc == calculated_crc, received_crc, calculated_crc


def build_response_packet(
    request_type: int,
    post_number: int,
    full_weight: int,
) -> bytes:
    """
    Формирует 8-байтный ответ посту на запрос 0x7A или 0x70.

    Args:
        request_type: Тип исходного запроса (0x7A или 0x70).
        post_number: Номер поста из запроса.
        full_weight: Целевой полный вес в граммах (для 0x7A).

    Returns:
        Готовый кадр с CRC.

    Raises:
        ValueError: Если тип запроса не поддерживает ответ.
    """
    if request_type == REQUEST_TYPE_FILL:
        response_type = RESPONSE_TYPE_FILL
    elif request_type == REQUEST_TYPE_FULL_WEIGHT:
        response_type = RESPONSE_TYPE_FULL_WEIGHT
    else:
        raise ValueError(f'Нельзя сформировать ответ для типа 0x{request_type:02X}')

    payload = struct.pack(
        '>BBBHB',
        response_type,
        post_number,
        0xFF,
        full_weight,
        0xFF,
    )
    return payload + struct.pack('>H', calc_crc(payload))
