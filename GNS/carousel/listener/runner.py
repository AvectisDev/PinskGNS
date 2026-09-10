"""
Основной цикл listener и логика переподключения.

Один процесс asyncio обслуживает несколько каруселей параллельно:
каждая — отдельная задача с собственным TCP-клиентом к NPort.

serial_exchange — чтение кадров, CRC, дедупликация, обработка, ответ, запись.
run_carousel — внешний цикл reconnect для одной карусели.
main — супервизор: gather по всем конфигам из окружения.
"""

from __future__ import annotations

import asyncio
import logging

from .cache import cache_request_result, get_cached_request
from .config import (
    FATAL_RESTART_DELAY_SECONDS,
    FRAME_SIZE,
    READ_TIMEOUT_SECONDS,
    RECONNECTABLE_ERRORS,
    RECONNECT_DELAY_SECONDS,
    CarouselInstanceConfig,
    load_carousel_configs,
)
from .processing import put_carousel_data, record_post_error, request_processing
from .protocol import build_response_packet, parse_request_frame, validate_frame_crc
from .transport import AsyncTcpTransport

logger = logging.getLogger('carousel')


async def serial_exchange(
    config: CarouselInstanceConfig,
    *,
    on_connected=None,
) -> None:
    """
    Обработка данных с постов одной карусели.

    Цикл: read_frame → CRC → dedup → request_processing → write → persist.
    Блокирующие Redis/ORM вызываются через asyncio.to_thread.
    """
    transport: AsyncTcpTransport | None = None
    try:
        transport = await AsyncTcpTransport.connect(
            config.tcp_host,
            config.tcp_port,
            READ_TIMEOUT_SECONDS,
        )
        if on_connected is not None:
            on_connected()

        while True:
            data = await transport.read_frame(FRAME_SIZE)

            if len(data) == FRAME_SIZE:
                logger.info(
                    "Карусель=%s получен запрос от поста - %s",
                    config.number,
                    data,
                )
                frame = parse_request_frame(data)

                crc_is_valid, received_crc, calculated_crc = (
                    validate_frame_crc(data)
                )
                if not crc_is_valid:
                    await asyncio.to_thread(
                        record_post_error,
                        config.number,
                        frame.post_number,
                        frame.request_type_str,
                        'invalid_crc',
                        f'Кадр={data.hex().upper()}, '
                        f'получен CRC={received_crc:04X}, '
                        f'рассчитан CRC={calculated_crc:04X}',
                        'crc_errors',
                    )
                    continue

                logger.info(
                    "Карусель=%s парсинг: тип=%s, пост=%s, "
                    "служебный байт=%02X, масса=%s, флаг=%02X",
                    config.number,
                    frame.request_type_str,
                    frame.post_number,
                    frame.service_byte,
                    frame.weight_combined,
                    frame.fill_flag,
                )

                is_duplicate, cached_response = get_cached_request(
                    config.number,
                    frame.request_type_str,
                    frame.post_number,
                    frame.weight_combined,
                )
                if is_duplicate:
                    if cached_response is not None:
                        await transport.write(cached_response)
                        logger.debug(
                            "Карусель=%s повторно отправлен ответ на пост: %s",
                            config.number,
                            cached_response.hex().upper(),
                        )
                    continue

                response_required, full_weight, process_data = (
                    await asyncio.to_thread(
                        request_processing,
                        config.number,
                        config.balloon_queue_key,
                        frame.request_type_str,
                        frame.post_number,
                        frame.weight_combined,
                    )
                )

                response_packet = None
                if response_required:
                    response_packet = build_response_packet(
                        frame.request_type,
                        frame.post_number,
                        full_weight,
                    )

                cache_request_result(
                    config.number,
                    frame.request_type_str,
                    frame.post_number,
                    frame.weight_combined,
                    response_packet,
                )

                if response_packet is not None:
                    await transport.write(response_packet)
                    logger.debug(
                        "Карусель=%s отправлен ответ на пост: %s",
                        config.number,
                        response_packet.hex().upper(),
                    )

                if process_data and isinstance(process_data, dict):
                    await asyncio.to_thread(
                        put_carousel_data,
                        config.number,
                        process_data,
                    )
            elif data:
                await asyncio.to_thread(
                    record_post_error,
                    config.number,
                    None,
                    None,
                    'invalid_frame_length',
                    f'Получено {len(data)} байт: {data.hex().upper()}',
                    'frame_errors',
                )

    finally:
        if transport is not None:
            await transport.close()
            logger.debug(
                "Карусель=%s соединение закрыто",
                config.number,
            )


async def run_carousel(config: CarouselInstanceConfig) -> None:
    """
    Внешний цикл переподключения для одной карусели.

    При обрыве — WARNING «Нет связи», затем INFO «Попытка подключения»
    и «Связь установлена» при успехе. Неожиданные ошибки — пауза
    FATAL_RESTART_DELAY_SECONDS.
    """
    logger.info(
        "Запуск обработки постов наполнения (карусель %s, NPort %s:%s).",
        config.number,
        config.tcp_host,
        config.tcp_port,
    )
    is_connected = False
    awaiting_reconnect_attempt_log = True

    def mark_connected() -> None:
        nonlocal is_connected, awaiting_reconnect_attempt_log
        is_connected = True
        awaiting_reconnect_attempt_log = False
        logger.info(
            "Карусель=%s связь установлена.",
            config.number,
        )

    while True:
        try:
            if awaiting_reconnect_attempt_log:
                logger.info(
                    "Карусель=%s попытка подключения к NPort %s:%s...",
                    config.number,
                    config.tcp_host,
                    config.tcp_port,
                )
                awaiting_reconnect_attempt_log = False
            await serial_exchange(config, on_connected=mark_connected)
        except RECONNECTABLE_ERRORS:
            if is_connected:
                logger.warning(
                    "Карусель=%s нет связи.",
                    config.number,
                )
            is_connected = False
            awaiting_reconnect_attempt_log = True
            await asyncio.sleep(RECONNECT_DELAY_SECONDS)
        except Exception as error:
            is_connected = False
            awaiting_reconnect_attempt_log = True
            logger.error(
                "Карусель=%s ошибка в serial_exchange: %s. "
                "Перезапуск через %s с...",
                config.number,
                error,
                FATAL_RESTART_DELAY_SECONDS,
            )
            await asyncio.sleep(FATAL_RESTART_DELAY_SECONDS)


async def main() -> None:
    """
    Точка входа listener-процесса.

    Загружает активные карусели из CarouselSettings и запускает
    параллельные задачи asyncio.
    """
    from carousel.settings_cache import load_from_db_and_publish

    await asyncio.to_thread(load_from_db_and_publish)
    configs = await asyncio.to_thread(load_carousel_configs)
    if not configs:
        logger.error(
            "Не найдено ни одной активной карусели в CarouselSettings "
            "(нужны is_active, tcp_host и rfid_reader)."
        )
        return

    logger.info(
        "Запуск listener для каруселей: %s",
        ', '.join(str(c.number) for c in configs),
    )
    await asyncio.gather(*(run_carousel(config) for config in configs))
