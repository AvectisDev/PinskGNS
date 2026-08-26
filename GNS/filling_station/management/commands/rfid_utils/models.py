"""Runtime-модели RFID: устройство FEIG, TCP-сессия и фильтр UID баллона."""

import asyncio
import os
from collections import deque
from typing import Dict
import logging

from .feig_frames import FeigProtocol

logger = logging.getLogger('rfid')

# UID баллонов в проекте — hex-строка, оканчивающаяся на этот суффикс (например ...1be0).
TAG_HEX_SUFFIX = os.getenv('RFID_TAG_HEX_SUFFIX', 'e0').strip().lower()


def is_balloon_nfc_tag(nfc_tag: str) -> bool:
    """
    True, если метка похожа на ожидаемый UID баллона: корректный hex и суффикс TAG_HEX_SUFFIX.
    Иные значения (шум, чужие транспондеры) логируются и не идут в бизнес-логику.

    Args:
        nfc_tag (str): Hex-строка UID метки.

    Returns:
        bool: ``True``, если метка проходит фильтр.
    """
    if not nfc_tag or not isinstance(nfc_tag, str):
        return False
    tag = nfc_tag.strip().lower()
    if not tag.endswith(TAG_HEX_SUFFIX):
        return False
    if len(tag) % 2 != 0:
        return False
    try:
        bytes.fromhex(tag)
    except ValueError:
        return False
    return True


class FeigReaderDevice:
    """Runtime-состояние RFID-считывателя FEIG (не Django-модель)."""

    def __init__(self, reader_settings):
        """
        Инициализирует runtime-ридер из записи ``ReaderSettings``.

        Args:
            reader_settings: Объект настроек ридера из БД.
        """
        self.number = reader_settings.number
        self.ip = reader_settings.ip
        self.port = reader_settings.port
        self.status = reader_settings.status
        self.function = reader_settings.function
        self.need_cache = reader_settings.need_cache
        self.input_state = 0
        self.previous_nfc_tags = deque(maxlen=5)

    def __str__(self):
        """
        Краткое строковое представление ридера.

        Returns:
            str: Номер, адрес и статус.
        """
        return f"Reader {self.number}: {self.ip}:{self.port} - {self.status}"

    def filter_duplicate_tag(self, nfc_tag: str) -> bool:
        """
        Кэширует 5 последних считанных меток.

        Args:
            nfc_tag (str): Hex UID метки.

        Returns:
            bool: ``True``, если метка новая (ещё не была в последних 5).
        """
        if nfc_tag in self.previous_nfc_tags:
            return False
        self.previous_nfc_tags.append(nfc_tag)
        return True


class ReaderSession:
    """
    Постоянная TCP-сессия к ридеру FEIG.

    Обеспечивает последовательную отправку команд и точное чтение ответа по длине (ALENGTH).
    """

    def __init__(self, reader: FeigReaderDevice):
        """
        Создаёт сессию без немедленного подключения.

        Args:
            reader: Runtime-ридер, к которому открывается TCP.
        """
        self.reader = reader
        self.conn = None
        self.writer = None
        self.lock = None

    async def connect(self):
        """Открывает TCP-соединение к ``reader.ip:reader.port``, если ещё не открыто."""
        if self.conn is None or self.writer is None:
            self.conn, self.writer = await asyncio.open_connection(self.reader.ip, self.reader.port)
            self.lock = asyncio.Lock()
            logger.info(f'{self.reader} TCP connected')

    async def close(self):
        """Закрывает TCP-соединение и сбрасывает состояние сессии."""
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

        Args:
            command_name (str): Имя команды FEIG.
            request_data (bytes): Поле DATA запроса.

        Returns:
            dict: Результат ``FeigProtocol.parse_response``.
        """
        req = FeigProtocol.create_request(command_name, request_data)
        return await self.send_raw(req, command_name)

    async def send_raw(self, frame: bytes, command_name: str = 'raw') -> Dict:
        """
        Отправляет готовый кадр FEIG (например команды лампы из settings.COMMANDS).

        Args:
            frame (bytes): Полный кадр запроса.
            command_name (str): Имя для логов.

        Returns:
            dict: Разобранный ответ или ``valid=False`` при ошибке/таймауте.
        """
        if self.conn is None or self.writer is None:
            await self.connect()

        async with self.lock:
            logger.debug(f'{self.reader.number} Отправляем запрос: {frame.hex()}, Команда {command_name}')
            self.writer.write(frame)
            await self.writer.drain()

            try:
                header = await asyncio.wait_for(self.conn.read(5), timeout=1.0)
                if len(header) < 5 or header[0] != FeigProtocol.STX:
                    return {'valid': False, 'error': 'Incomplete/invalid header'}

                length = int.from_bytes(header[1:3], 'big')
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
                self.conn = None
                self.writer = None
                return {'valid': False, 'error': str(e)}

    async def indicate_tag_read(self, success: bool) -> Dict:
        """
        Зелёная лампа: постоянное свечение при успехе, мигание при ошибке.

        Args:
            success (bool): Успешная обработка метки.

        Returns:
            dict: Ответ ридера на команду SET_OUTPUT.
        """
        from .settings import command_frame

        name = 'read_complete' if success else 'read_complete_with_error'
        result = await self.send_raw(command_frame(name), command_name=name)
        if result.get('valid'):
            logger.info(f'{self.reader.number} Лампа: {name}')
        else:
            logger.warning(f'{self.reader.number} Лампа {name} не принята: {result}')
        return result

    async def send_event_ack(self, event_command: int, status: int = 0x00) -> Dict:
        """
        ACK для Notification Mode event. COMMAND=event_command, DATA[0]=STATUS.

        Args:
            event_command (int): Код события.
            status (int): Байт статуса ACK.

        Returns:
            dict: Ответ ридера.
        """
        return await self.send_by_code(event_command, bytes([status]))

    async def send_by_code(self, command_code: int, request_data: bytes = b'') -> Dict:
        """
        Отправляет команду по числовому коду.

        Args:
            command_code (int): Код команды FEIG.
            request_data (bytes): Поле DATA.

        Returns:
            dict: Результат ``send_raw``.
        """
        req = FeigProtocol.create_request_by_code(command_code, request_data)
        return await self.send_raw(req, command_name=f'0x{command_code:02X}')
