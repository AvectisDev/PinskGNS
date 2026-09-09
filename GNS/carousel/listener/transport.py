"""
TCP-транспорт к NPort W2150A в режиме TCP Server.

Асинхронный клиент: соединение держится открытым; байты с RS-485
приходят push-потоком. Частичные TCP-сегменты накапливаются до полного
кадра (FRAME_SIZE).
"""

from __future__ import annotations

import asyncio
import logging
import time

from .config import FRAME_SIZE, STALE_PARTIAL_BUFFER_SECONDS

logger = logging.getLogger('carousel')


class PartialBufferStaleError(ConnectionError):
    """Неполный кадр в буфере не дополнен за STALE_PARTIAL_BUFFER_SECONDS."""


class AsyncTcpTransport:
    """
    Асинхронный TCP-клиент к NPort.

    Соединение держится открытым; данные с RS-485 пушатся в сокет без polling.
    Частичные TCP-сегменты накапливаются в буфере до полного кадра.
    """

    def __init__(
        self,
        host: str,
        port: int,
        timeout: float,
        *,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        self._host = host
        self._port = port
        self._timeout = timeout
        self._reader = reader
        self._writer = writer
        self._buffer = bytearray()
        self._partial_buffer_since: float | None = None

    @classmethod
    async def connect(
        cls,
        host: str,
        port: int,
        timeout: float,
    ) -> AsyncTcpTransport:
        """Устанавливает TCP-соединение с NPort."""
        if not host:
            raise ValueError('Задайте tcp_host в CarouselSettings')
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=timeout,
            )
        except TimeoutError as error:
            raise TimeoutError(
                f'Таймаут подключения к NPort {host}:{port}'
            ) from error
        return cls(host, port, timeout, reader=reader, writer=writer)

    def _reset_partial_buffer_timer(self) -> None:
        self._partial_buffer_since = None

    def _handle_read_timeout(self, size: int) -> bytes:
        """
        Обрабатывает таймаут чтения: пустой кадр или stale partial.

        Raises:
            PartialBufferStaleError: Неполный кадр висит слишком долго.
        """
        if self._buffer:
            if self._partial_buffer_since is None:
                self._partial_buffer_since = time.monotonic()
            elif (
                time.monotonic() - self._partial_buffer_since
                >= STALE_PARTIAL_BUFFER_SECONDS
            ):
                stale = bytes(self._buffer)
                self._buffer.clear()
                self._reset_partial_buffer_timer()
                logger.debug(
                    "TCP: сброс зависшего неполного буфера: %s",
                    stale.hex().upper(),
                )
                raise PartialBufferStaleError(
                    'Неполный кадр в буфере не дополнен'
                )
            logger.debug(
                "TCP: таймаут, неполный кадр в буфере (%s/%s байт): %s",
                len(self._buffer),
                size,
                bytes(self._buffer).hex().upper(),
            )
        return b''

    async def read_frame(self, size: int = FRAME_SIZE) -> bytes:
        """
        Читает один кадр из TCP-потока.

        При таймауте без данных возвращает пустые байты — цикл listener
        продолжает ждать. Если в буфере есть неполный кадр дольше
        STALE_PARTIAL_BUFFER_SECONDS, сбрасывает буфер и поднимает
        PartialBufferStaleError для переподключения.
        """
        while len(self._buffer) < size:
            try:
                chunk = await asyncio.wait_for(
                    self._reader.read(max(size - len(self._buffer), 1)),
                    timeout=self._timeout,
                )
            except TimeoutError:
                return self._handle_read_timeout(size)
            if not chunk:
                raise ConnectionError('NPort закрыл TCP-соединение')
            if not self._buffer:
                self._partial_buffer_since = time.monotonic()
            logger.debug(
                "TCP: получено %s байт: %s",
                len(chunk),
                chunk.hex().upper(),
            )
            self._buffer.extend(chunk)

        frame = bytes(self._buffer[:size])
        del self._buffer[:size]
        self._reset_partial_buffer_timer()
        logger.debug(
            "TCP: собран кадр %s байт: %s",
            len(frame),
            frame.hex().upper(),
        )
        return frame

    async def write(self, data: bytes) -> None:
        """Отправляет ответ посту через NPort."""
        logger.debug(
            "TCP: отправлено %s байт: %s",
            len(data),
            data.hex().upper(),
        )
        self._writer.write(data)
        await self._writer.drain()

    async def close(self) -> None:
        """Закрывает TCP-соединение."""
        self._writer.close()
        try:
            await self._writer.wait_closed()
        except Exception:
            pass


async def read_exact(reader: asyncio.StreamReader, size: int) -> bytes:
    """
    Читает ровно size байт из StreamReader.

    Используется в тестах для проверки сборки кадра из фрагментов.

    Raises:
        ConnectionError: Соединение закрыто до получения полного кадра.
    """
    buffer = bytearray()
    while len(buffer) < size:
        chunk = await reader.read(size - len(buffer))
        if not chunk:
            raise ConnectionError(
                'Соединение закрыто до получения полного кадра'
            )
        buffer.extend(chunk)
    return bytes(buffer)
