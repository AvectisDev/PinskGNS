"""
Основной цикл listener и логика переподключения.

serial_exchange — чтение кадров, CRC, дедупликация, обработка, ответ, запись.
main — внешний цикл с тихим retry каждые RECONNECT_DELAY_SECONDS.
"""

import logging
import time

from .cache import cache_request_result, get_cached_request
from .config import (
    CAROUSEL_NUMBER,
    FATAL_RESTART_DELAY_SECONDS,
    FRAME_SIZE,
    READ_TIMEOUT_SECONDS,
    RECONNECTABLE_ERRORS,
    RECONNECT_DELAY_SECONDS,
    TCP_HOST,
    TCP_PORT,
)
from .processing import put_carousel_data, record_post_error, request_processing
from .protocol import build_response_packet, parse_request_frame, validate_frame_crc
from .transport import TcpTransport

logger = logging.getLogger('carousel')


def serial_exchange(
    *,
    on_connected=None,
) -> None:
    """
    Обработка данных с постов наполнения баллонов.

    Цикл: read_frame → CRC → dedup → request_processing → write → persist.
    Каждый пост отправляет FRAME_SIZE байт, после чего ждёт ответ.
    """
    transport: TcpTransport | None = None
    try:
        transport = TcpTransport(TCP_HOST, TCP_PORT, READ_TIMEOUT_SECONDS)
        if on_connected is not None:
            on_connected()

        while True:
            data = transport.read_frame(FRAME_SIZE)

            if len(data) == FRAME_SIZE:
                logger.info(f"Получен запрос от поста - {data}")
                frame = parse_request_frame(data)

                crc_is_valid, received_crc, calculated_crc = (
                    validate_frame_crc(data)
                )
                if not crc_is_valid:
                    record_post_error(
                        frame.post_number,
                        frame.request_type_str,
                        'invalid_crc',
                        f'Кадр={data.hex().upper()}, '
                        f'получен CRC={received_crc:04X}, '
                        f'рассчитан CRC={calculated_crc:04X}',
                        metric_name='crc_errors',
                    )
                    continue

                logger.info(
                    f"Парсинг: тип={frame.request_type_str}, "
                    f"пост={frame.post_number}, "
                    f"служебный байт={frame.service_byte:02X}, "
                    f"масса={frame.weight_combined}, флаг={frame.fill_flag:02X}"
                )

                is_duplicate, cached_response = get_cached_request(
                    frame.request_type_str,
                    frame.post_number,
                    frame.weight_combined,
                )
                if is_duplicate:
                    if cached_response is not None:
                        transport.write(cached_response)
                        logger.debug(
                            "Повторно отправлен ответ на пост: "
                            f"{cached_response.hex().upper()}"
                        )
                    continue

                response_required, full_weight, process_data = (
                    request_processing(
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
                    frame.request_type_str,
                    frame.post_number,
                    frame.weight_combined,
                    response_packet,
                )

                if response_packet is not None:
                    transport.write(response_packet)
                    logger.debug(
                        f"Отправлен ответ на пост: "
                        f"{response_packet.hex().upper()}"
                    )

                if process_data and isinstance(process_data, dict):
                    put_carousel_data(process_data)
            elif data:
                record_post_error(
                    None,
                    None,
                    'invalid_frame_length',
                    f'Получено {len(data)} байт: {data.hex().upper()}',
                    metric_name='frame_errors',
                )

    finally:
        if transport is not None:
            transport.close()
            logger.debug("Соединение закрыто")


def main() -> None:
    """
    Точка входа listener-процесса.

    Внешний цикл переподключения: при обрыве — WARNING «Нет связи»,
    затем INFO «Попытка подключения» и «Связь установлена» при успехе.
    Неожиданные ошибки — пауза FATAL_RESTART_DELAY_SECONDS.
    """
    logger.info(
        "Запуск обработки постов наполнения (карусель %s).",
        CAROUSEL_NUMBER,
    )
    is_connected = False
    awaiting_reconnect_attempt_log = True

    def mark_connected() -> None:
        nonlocal is_connected, awaiting_reconnect_attempt_log
        is_connected = True
        awaiting_reconnect_attempt_log = False
        logger.info("Связь с каруселью установлена.")

    while True:
        try:
            if awaiting_reconnect_attempt_log:
                logger.info(
                    "Попытка подключения к карусели (NPort %s:%s)...",
                    TCP_HOST,
                    TCP_PORT,
                )
                awaiting_reconnect_attempt_log = False
            serial_exchange(on_connected=mark_connected)
        except RECONNECTABLE_ERRORS:
            if is_connected:
                logger.warning("Нет связи с каруселью.")
            is_connected = False
            awaiting_reconnect_attempt_log = True
            time.sleep(RECONNECT_DELAY_SECONDS)
        except Exception as error:
            is_connected = False
            awaiting_reconnect_attempt_log = True
            logger.error(
                "Ошибка в serial_exchange: %s. Перезапуск через %s с...",
                error,
                FATAL_RESTART_DELAY_SECONDS,
            )
            time.sleep(FATAL_RESTART_DELAY_SECONDS)
