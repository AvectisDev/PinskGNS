"""
Конфигурация экземпляров listener карусели.

Читается из переменных окружения. Один процесс обслуживает все карусели,
у которых задан ``CAROUSEL_<N>_TCP_HOST``:

    CAROUSEL_<N>_TCP_HOST   — IP NPort (обязателен для включения инстанса)
    CAROUSEL_<N>_TCP_PORT   — TCP-порт NPort (по умолчанию 4001)
    CAROUSEL_<N>_RFID_READER — номер RFID-считывателя для очереди паспортов
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from core.redis_queue import get_reader_balloon_queue_key

MAX_CAROUSEL_SCAN = 16

FRAME_SIZE = 8
READ_TIMEOUT_SECONDS = 1.0
REQUEST_CACHE_SECONDS = 2.0
RECONNECT_DELAY_SECONDS = 60
FATAL_RESTART_DELAY_SECONDS = 300
STALE_PARTIAL_BUFFER_SECONDS = 10.0

RECONNECTABLE_ERRORS = (
    ConnectionError,
    TimeoutError,
    OSError,
)


@dataclass(frozen=True)
class CarouselInstanceConfig:
    """Параметры одного TCP-клиента к NPort карусели."""

    number: int
    tcp_host: str
    tcp_port: int
    rfid_reader: int
    balloon_queue_key: str

    @property
    def env_prefix(self) -> str:
        return f'CAROUSEL_{self.number}'


def _load_instance(number: int) -> CarouselInstanceConfig | None:
    """Собирает конфиг карусели N, если задан TCP_HOST."""
    prefix = f'CAROUSEL_{number}'
    tcp_host = os.getenv(f'{prefix}_TCP_HOST', '').strip()
    if not tcp_host:
        return None

    tcp_port = int(os.getenv(f'{prefix}_TCP_PORT', '4001'))
    rfid_reader = int(os.getenv(f'{prefix}_RFID_READER', '8'))
    return CarouselInstanceConfig(
        number=number,
        tcp_host=tcp_host,
        tcp_port=tcp_port,
        rfid_reader=rfid_reader,
        balloon_queue_key=get_reader_balloon_queue_key(rfid_reader),
    )


def load_carousel_configs() -> list[CarouselInstanceConfig]:
    """
    Возвращает конфиги всех каруселей с заданным ``CAROUSEL_<N>_TCP_HOST``.

    Сканирует номера 1..MAX_CAROUSEL_SCAN. Обратная совместимость:
    достаточно задать ``CAROUSEL_1_TCP_HOST`` (или любой один N) — процесс
    запустит только найденные инстансы.
    """
    configs: list[CarouselInstanceConfig] = []
    for number in range(1, MAX_CAROUSEL_SCAN + 1):
        instance = _load_instance(number)
        if instance is not None:
            configs.append(instance)
    return configs
