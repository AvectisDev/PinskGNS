"""Упаковка ASCII-строк в Melsoft ARRAY [0..16] OF WORD (17 UInt16).

Формат GX Works2 String(32) в D-регистрах:
- два символа в одном WORD (младший байт — первый символ);
- после строки нулевой терминатор;
- область 34 байта → 17 WORD.
"""

from __future__ import annotations

import logging
from typing import Any, Sequence

logger = logging.getLogger('opcua')

MELSOFT_STRING_WORD_COUNT = 17
MELSOFT_STRING_MAX_CHARS = 32
MELSOFT_STRING_BYTE_LEN = 34  # 32 символа + терминатор + выравнивание

# Теги vehicle_select, которые на ПЛК — WORD[17], не OPC String.
VEHICLE_SELECT_WORD_BUFFERS = frozenset({
    'proposed_truck_number',
    'proposed_trailer_number',
    *(f'vehicle_list_{i}' for i in range(8)),
})


def empty_melsoft_words() -> list[int]:
    """Буфер из 17 нулей (пустая строка на ПЛК)."""
    return [0] * MELSOFT_STRING_WORD_COUNT


def pack_melsoft_string(text: Any) -> list[int]:
    """
    Упаковывает ASCII-строку в 17 UInt16 (порядок Mitsubishi).

    Не-ASCII или ошибка кодирования → 17 нулей и warning в лог.
    """
    if text is None:
        return empty_melsoft_words()
    raw_text = str(text)
    if not raw_text:
        return empty_melsoft_words()
    try:
        raw = raw_text.encode('ascii')
    except UnicodeEncodeError:
        logger.warning(
            'Melsoft WORD-буфер: не-ASCII строка %r — пишем нули',
            raw_text[:40],
        )
        return empty_melsoft_words()
    if len(raw) > MELSOFT_STRING_MAX_CHARS:
        raw = raw[:MELSOFT_STRING_MAX_CHARS]
    raw = (raw + b'\x00').ljust(MELSOFT_STRING_BYTE_LEN, b'\x00')
    return [
        raw[i] | (raw[i + 1] << 8)
        for i in range(0, MELSOFT_STRING_BYTE_LEN, 2)
    ]


def unpack_melsoft_string(words: Any) -> str:
    """
    Распаковывает 17 WORD (или меньше) в ASCII-строку до первого нулевого байта.

    Строка или None возвращаются как str(words) / '' без распаковки слов.
    """
    if words is None:
        return ''
    if isinstance(words, str):
        return words
    if isinstance(words, (bytes, bytearray)):
        return words.split(b'\x00', 1)[0].decode('ascii', errors='ignore')
    if not isinstance(words, (list, tuple)):
        return str(words)

    parts: list[int] = []
    for item in words:
        try:
            word = int(item) & 0xFFFF
        except (TypeError, ValueError):
            break
        lo = word & 0xFF
        hi = (word >> 8) & 0xFF
        if lo == 0:
            break
        parts.append(lo)
        if hi == 0:
            break
        parts.append(hi)
    if not parts:
        return ''
    return bytes(parts).decode('ascii', errors='ignore')


def is_empty_melsoft_buffer(value: Any) -> bool:
    """True если буфер пуст: None, '', все нули, или строка из пробелов."""
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, tuple)):
        if not value:
            return True
        try:
            return all(int(item) == 0 for item in value)
        except (TypeError, ValueError):
            return False
    return False


def coerce_vehicle_select_text(value: Any) -> str:
    """Значение тега vehicle_select → текстовая строка для парсеров."""
    if is_empty_melsoft_buffer(value):
        return ''
    if isinstance(value, (list, tuple)):
        return unpack_melsoft_string(value)
    if value is None:
        return ''
    return str(value)


def is_vehicle_select_word_buffer(tag_name: str) -> bool:
    """Имя полного или короткого тега — WORD[17] буфер vehicle_select."""
    short = tag_name
    if short.startswith('autogas.vehicle_select.'):
        short = short[len('autogas.vehicle_select.'):]
    return short in VEHICLE_SELECT_WORD_BUFFERS


def looks_like_melsoft_word_array(value: Any) -> bool:
    """Значение уже упаковано в 17 (или близко) целых для UInt16-записи."""
    if not isinstance(value, (list, tuple)):
        return False
    if not value:
        return False
    if len(value) > MELSOFT_STRING_WORD_COUNT:
        return False
    return all(isinstance(item, int) and not isinstance(item, bool) for item in value)
