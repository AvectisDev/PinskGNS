"""
Конфигурация экземпляров listener карусели.

Загружается из ``CarouselSettings`` (активные записи с TCP host и RFID).
Один процесс обслуживает все активные карусели параллельно.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from core.redis_queue import get_reader_balloon_queue_key

logger = logging.getLogger('carousel')

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


def load_carousel_configs() -> list[CarouselInstanceConfig]:
    """
    Возвращает конфиги всех активных каруселей из БД.

    Пропускает ``is_active`` записи без ``tcp_host`` или без ``rfid_reader``
    (WARNING в лог).
    """
    from carousel.models import CarouselSettings

    rows = list(
        CarouselSettings.objects.filter(is_active=True)
        .select_related('rfid_reader')
        .order_by('number')
    )

    configs: list[CarouselInstanceConfig] = []
    for settings in rows:
        tcp_host = (settings.tcp_host or '').strip()
        if not tcp_host:
            logger.warning(
                "Карусель number=%s активна, но tcp_host пуст — пропуск",
                settings.number,
            )
            continue
        if settings.rfid_reader_id is None:
            logger.warning(
                "Карусель number=%s активна, но rfid_reader не задан — пропуск",
                settings.number,
            )
            continue

        rfid_reader = int(settings.rfid_reader_id)
        configs.append(
            CarouselInstanceConfig(
                number=settings.number,
                tcp_host=tcp_host,
                tcp_port=int(settings.tcp_port),
                rfid_reader=rfid_reader,
                balloon_queue_key=get_reader_balloon_queue_key(rfid_reader),
            )
        )
    return configs
