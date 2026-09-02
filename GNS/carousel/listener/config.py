"""
Конфигурация экземпляра listener карусели.

Читается из переменных окружения при импорте модуля.
Для нескольких каруселей запускается отдельный процесс с собственным
``CAROUSEL_NUMBER`` и префиксом ``CAROUSEL_<N>_``:

    CAROUSEL_<N>_TCP_HOST   — IP NPort (обязателен)
    CAROUSEL_<N>_TCP_PORT   — TCP-порт NPort (по умолчанию 4001)
    CAROUSEL_<N>_RFID_READER — номер RFID-считывателя для очереди паспортов
"""

import os
import socket

from core.redis_queue import get_reader_balloon_queue_key

CAROUSEL_NUMBER = int(os.getenv('CAROUSEL_NUMBER', '1'))
CAROUSEL_ENV_PREFIX = f'CAROUSEL_{CAROUSEL_NUMBER}'
TCP_HOST = os.getenv(f'{CAROUSEL_ENV_PREFIX}_TCP_HOST', '').strip()
TCP_PORT = int(os.getenv(f'{CAROUSEL_ENV_PREFIX}_TCP_PORT', '4001'))
RFID_READER_NUMBER = int(
    os.getenv(f'{CAROUSEL_ENV_PREFIX}_RFID_READER', '8')
)
BALLOON_QUEUE_KEY = get_reader_balloon_queue_key(RFID_READER_NUMBER)

FRAME_SIZE = 8
READ_TIMEOUT_SECONDS = 1.0
REQUEST_CACHE_SECONDS = 2.0
RECONNECT_DELAY_SECONDS = 60
FATAL_RESTART_DELAY_SECONDS = 300
STALE_PARTIAL_BUFFER_SECONDS = 10.0

RECONNECTABLE_ERRORS = (
    ConnectionError,
    TimeoutError,
    socket.timeout,
    socket.gaierror,
)
