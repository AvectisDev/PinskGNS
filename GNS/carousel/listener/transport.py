"""
TCP-транспорт к NPort W2150A в режиме TCP Server.

Соединение держится открытым; байты с RS-485 приходят push-потоком.
Частичные TCP-сегменты накапливаются до полного кадра (FRAME_SIZE).
"""

import logging
import socket
import time

from .config import (
    CAROUSEL_ENV_PREFIX,
    FRAME_SIZE,
    STALE_PARTIAL_BUFFER_SECONDS,
)

logger = logging.getLogger('carousel')


class PartialBufferStaleError(ConnectionError):
    """Неполный кадр в буфере не дополнен за STALE_PARTIAL_BUFFER_SECONDS."""


class TcpTransport:
    """
    TCP-клиент к NPort.

    Соединение держится открытым; данные с RS-485 пушатся в сокет без polling.
    Частичные TCP-сегменты накапливаются в буфере до полного кадра.
    """

    def __init__(self, host: str, port: int, timeout: float) -> None:
        if not host:
            raise ValueError(
                f'Задайте {CAROUSEL_ENV_PREFIX}_TCP_HOST'
            )
        self._buffer = bytearray()
        self._partial_buffer_since: float | None = None
        self._sock = socket.create_connection((host, port), timeout=timeout)
        self._sock.settimeout(timeout)

    def _reset_partial_buffer_timer(self) -> None:
        self._partial_buffer_since = None

    def read_frame(self, size: int = FRAME_SIZE) -> bytes:
        """
        Читает один кадр из TCP-потока.

        При таймауте без данных возвращает пустые байты — цикл listener
        продолжает ждать. Если в буфере есть неполный кадр дольше
        STALE_PARTIAL_BUFFER_SECONDS, сбрасывает буфер и поднимает
        PartialBufferStaleError для переподключения (например, после
        обесточивания карусели с «зависшими» 2 байтами CRC).
        """
        while len(self._buffer) < size:
            try:
                chunk = self._sock.recv(max(size - len(self._buffer), 1))
            except socket.timeout:
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

    def write(self, data: bytes) -> None:
        """Отправляет ответ посту через NPort."""
        logger.debug(
            "TCP: отправлено %s байт: %s",
            len(data),
            data.hex().upper(),
        )
        self._sock.sendall(data)

    def close(self) -> None:
        """Закрывает TCP-соединение."""
        try:
            self._sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self._sock.close()


def recv_exact(sock: socket.socket, size: int) -> bytes:
    """
    Читает ровно size байт из сокета.

    Используется в тестах для проверки сборки кадра из фрагментов.

    Raises:
        ConnectionError: Соединение закрыто до получения полного кадра.
    """
    buffer = bytearray()
    while len(buffer) < size:
        chunk = sock.recv(size - len(buffer))
        if not chunk:
            raise ConnectionError('Соединение закрыто до получения полного кадра')
        buffer.extend(chunk)
    return bytes(buffer)
