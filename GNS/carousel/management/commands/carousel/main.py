import os
import socket
import struct
import logging.config
import django
import time
from dataclasses import dataclass


# Инициализация Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'GNS.settings')
django.setup()

from django.core.exceptions import ValidationError

from carousel.validation import is_value_in_range
from carousel.services import (
    CarouselPostNotFoundError,
    UnsupportedCarouselRequestError,
    get_carousel_settings_data,
    process_carousel_data_direct,
)
from core.redis_queue import (
    get_reader_balloon_queue_key,
    increment_metric,
    pop_json_from_queue,
)

# Конфигурация логирования из настроек Django
logging.config.dictConfig(django.conf.settings.LOGGING)
logger = logging.getLogger('carousel')

# Настройки экземпляра карусели. Для нескольких каруселей запускается по одному
# процессу с собственным CAROUSEL_NUMBER и переменными CAROUSEL_<N>_*.
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
WAIT_DATA_LOG_INTERVAL_SECONDS = 60.0

RECONNECTABLE_ERRORS = (
    ConnectionError,
    TimeoutError,
    socket.timeout,
    socket.gaierror,
)


@dataclass(frozen=True)
class CachedRequest:
    expires_at: float
    response_packet: bytes | None


recent_requests: dict[tuple[str, int, int], CachedRequest] = {}


class TcpTransport:
    """
    TCP-клиент к NPort в режиме TCP Server.

    Соединение держится открытым; данные с RS-485 пушатся в сокет без polling.
    Частичные TCP-сегменты накапливаются в буфере до полного кадра.
    """

    def __init__(self, host: str, port: int, timeout: float) -> None:
        if not host:
            raise ValueError(
                f'Задайте {CAROUSEL_ENV_PREFIX}_TCP_HOST'
            )
        self._buffer = bytearray()
        self._sock = socket.create_connection((host, port), timeout=timeout)
        self._sock.settimeout(timeout)

    def read_frame(self, size: int = FRAME_SIZE) -> bytes:
        while len(self._buffer) < size:
            try:
                chunk = self._sock.recv(max(size - len(self._buffer), 1))
            except socket.timeout:
                if self._buffer:
                    logger.debug(
                        "TCP: таймаут, неполный кадр в буфере (%s/%s байт): %s",
                        len(self._buffer),
                        size,
                        bytes(self._buffer).hex().upper(),
                    )
                return b''
            if not chunk:
                raise ConnectionError('NPort закрыл TCP-соединение')
            logger.debug(
                "TCP: получено %s байт: %s",
                len(chunk),
                chunk.hex().upper(),
            )
            self._buffer.extend(chunk)

        frame = bytes(self._buffer[:size])
        del self._buffer[:size]
        logger.debug(
            "TCP: собран кадр %s байт: %s",
            len(frame),
            frame.hex().upper(),
        )
        return frame

    def write(self, data: bytes) -> None:
        logger.debug(
            "TCP: отправлено %s байт: %s",
            len(data),
            data.hex().upper(),
        )
        self._sock.sendall(data)

    def close(self) -> None:
        try:
            self._sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self._sock.close()


def recv_exact(sock: socket.socket, size: int) -> bytes:
    """
    Читает ровно size байт из сокета (для тестов и низкоуровневой сборки кадра).
    При закрытии соединения поднимает ConnectionError.
    """
    buffer = bytearray()
    while len(buffer) < size:
        chunk = sock.recv(size - len(buffer))
        if not chunk:
            raise ConnectionError('Соединение закрыто до получения полного кадра')
        buffer.extend(chunk)
    return bytes(buffer)


def open_transport() -> TcpTransport:
    logger.info(
        "Подключение к NPort по TCP %s:%s (карусель=%s)",
        TCP_HOST,
        TCP_PORT,
        CAROUSEL_NUMBER,
    )
    return TcpTransport(TCP_HOST, TCP_PORT, READ_TIMEOUT_SECONDS)


@dataclass(frozen=True)
class PostSettings:
    available: bool
    read_only: bool
    weight_correction: float | None
    min_balloon_weight_from: float | None
    min_balloon_weight_to: float | None
    max_balloon_weight_from: float | None
    max_balloon_weight_to: float | None
    passport_weight_diff_from: float | None
    passport_weight_diff_to: float | None


def record_post_error(
    post_number: int | None,
    request_type: str | None,
    error_code: str,
    message: str,
    metric_name: str = 'post_errors',
) -> None:
    logger.error(
        "Карусель=%s пост=%s тип=%s ошибка=%s: %s",
        CAROUSEL_NUMBER,
        post_number,
        request_type,
        error_code,
        message,
    )
    try:
        increment_metric(CAROUSEL_NUMBER, metric_name)
    except Exception as error:
        logger.error(f"Не удалось обновить метрику {metric_name}: {error}")


def get_and_remove_last_balloon(
    post_number: int,
    request_type: str,
) -> tuple[dict | None, bool]:
    """
    Атомарно извлекает самый старый паспорт из нативной Redis-очереди.
    """
    try:
        balloon, queue_size = pop_json_from_queue(BALLOON_QUEUE_KEY)
        logger.debug(
            f"Карусель={CAROUSEL_NUMBER} очередь={BALLOON_QUEUE_KEY} "
            f"размер={queue_size}"
        )
        return balloon, True
    except Exception as error:
        record_post_error(
            post_number,
            request_type,
            'queue_read_error',
            str(error),
            metric_name='queue_errors',
        )
        return None, False


def put_carousel_data(data: dict) -> bool:
    """
    Сохраняет показания поста карусели напрямую через сервис Django.

    Пост передаёт данные по TCP (NPort) в виде набора байт по
    проприетарному протоколу, поэтому listener преобразует их в словарь
    и передаёт напрямую в бизнес-логику приложения.
    :param data: Содержит словарь с ключами 'request_type'-тип запроса с поста наполнения, 'post_number' -
    номер поста наполнения, 'weight_combined'- текущий вес баллона, который находится на посту наполнения
    :return: True при успешном сохранении
    """
    try:
        logger.info(f"Данные с поста переданы в Django: {data}")
        process_carousel_data_direct(data)
        logger.info("Данные с поста успешно сохранены")
        return True
    except (
        ValidationError,
        CarouselPostNotFoundError,
        UnsupportedCarouselRequestError,
    ) as error:
        record_post_error(
            data.get('post_number'),
            data.get('request_type'),
            'persistence_validation_error',
            str(error),
        )
    except Exception as error:
        record_post_error(
            data.get('post_number'),
            data.get('request_type'),
            'persistence_error',
            str(error),
        )
        logger.exception("Ошибка сохранения данных с поста наполнения")
    return False


def calc_crc(message: bytes) -> int:
    """
    вычисляет CRC-16/AUG-CCITT
    """
    poly = 0x1021
    reg = 0xFFFF
    message += b'\x00\x00'
    for byte in message:
        mask = 0x80
        while (mask > 0):
            reg <<= 1
            if byte & mask:
                reg += 1
            mask >>= 1
            if reg > 0xffff:
                reg &= 0xffff
                reg ^= poly
    return reg


def validate_frame_crc(frame: bytes) -> tuple[bool, int, int]:
    """Проверяет CRC16/SPI-FUJITSU первых шести байт кадра."""
    if len(frame) != 8:
        return False, 0, 0
    received_crc = int.from_bytes(frame[6:8], byteorder='big')
    calculated_crc = calc_crc(frame[:6])
    return received_crc == calculated_crc, received_crc, calculated_crc


def build_response_packet(
    request_type: int,
    post_number: int,
    full_weight: int,
) -> bytes:
    if request_type == 0x7A:
        response_type = 0x5A
    elif request_type == 0x70:
        response_type = 0x50
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


def check_settings(post_number: int) -> PostSettings:
    """
    Читает настройки обработки постов из базы данных.
    """
    post_settings = get_carousel_settings_data()
    if not post_settings:
        return PostSettings(
            available=False,
            read_only=True,
            weight_correction=0.0,
            min_balloon_weight_from=None,
            min_balloon_weight_to=None,
            max_balloon_weight_from=None,
            max_balloon_weight_to=None,
            passport_weight_diff_from=None,
            passport_weight_diff_to=None,
        )

    weight_correction = 0.0
    if post_settings.get('use_weight_management'):
        if post_settings.get('use_common_correction'):
            weight_correction = post_settings.get('weight_correction_value')
        else:
            weight_correction = post_settings.get(
                f'post_{post_number}_correction'
            )

    return PostSettings(
        available=True,
        read_only=bool(post_settings.get('read_only')),
        weight_correction=weight_correction,
        min_balloon_weight_from=post_settings.get('min_balloon_weight_from'),
        min_balloon_weight_to=post_settings.get('min_balloon_weight_to'),
        max_balloon_weight_from=post_settings.get('max_balloon_weight_from'),
        max_balloon_weight_to=post_settings.get('max_balloon_weight_to'),
        passport_weight_diff_from=post_settings.get('passport_weight_diff_from'),
        passport_weight_diff_to=post_settings.get('passport_weight_diff_to'),
    )


def check_balloon_size(weight: int) -> int:
    """
    определяет объём баллона по весу пустого баллона, который передаёт пост наполнения.
    :param weight: Вес баллона перед наполнением
    :return: int: Объём баллона
    """
    balloon_size = 50
    # if weight <= 12000:
    #     balloon_size = 27
    # elif 14000 < weight < 25000:
    #     balloon_size = 50

    return balloon_size


def get_cached_request(
    request_type: str,
    post_number: int,
    weight: int,
) -> tuple[bool, bytes | None]:
    """Возвращает сохранённый ответ на повторный запрос контроллера."""
    now = time.monotonic()
    expired_keys = [
        key for key, request in recent_requests.items()
        if request.expires_at <= now
    ]
    for key in expired_keys:
        recent_requests.pop(key, None)

    request_key = (request_type, post_number, weight)
    cached_request = recent_requests.get(request_key)
    if cached_request is None:
        return False, None

    logger.debug(f"Повторный запрос {request_key}: используется сохранённый ответ")
    return True, cached_request.response_packet


def cache_request_result(
    request_type: str,
    post_number: int,
    weight: int,
    response_packet: bytes | None,
) -> None:
    request_key = (request_type, post_number, weight)
    recent_requests[request_key] = CachedRequest(
        expires_at=time.monotonic() + REQUEST_CACHE_SECONDS,
        response_packet=response_packet,
    )


def request_processing(request_type: str, post_number: int, weight: int) -> tuple[bool, int, dict]:
    """
    Обрабатывает запрос от поста наполнения.
    :return:
        - response_required: нужно ли отправлять ответ на пост наполнения
        - full_weight: необходимый вес полного баллона (в граммах)
        - process_data_to_server: данные для отправки на сервер
    """
    response_required = False
    full_weight = 0
    process_data_to_server = {
        'carousel_number': CAROUSEL_NUMBER,
        'request_type': request_type,
        'post_number': post_number,
        'size': check_balloon_size(weight)
    }

    if request_type == '0x7a':
        logger.debug(f"Запрос 0x7a")

        balloon_from_cache, queue_available = get_and_remove_last_balloon(
            post_number,
            request_type,
        )

        if balloon_from_cache is None:
            if queue_available:
                record_post_error(
                    post_number,
                    request_type,
                    'empty_balloon_queue',
                    f'В очереди {BALLOON_QUEUE_KEY} нет паспорта баллона',
                    metric_name='empty_queue',
                )
            process_data_to_server.update({
                'is_empty': True,
                'empty_weight': weight / 1000
            })
            return response_required, full_weight, process_data_to_server

        filling_status = bool(balloon_from_cache.get('filling_status'))
        netto = balloon_from_cache.get('netto')
        brutto = balloon_from_cache.get('brutto')

        if not filling_status:
            record_post_error(
                post_number,
                request_type,
                'balloon_not_ready',
                'Паспорт баллона не разрешает наполнение',
                metric_name='passport_errors',
            )
        elif netto is None or brutto is None:
            record_post_error(
                post_number,
                request_type,
                'incomplete_passport',
                f'Неполный паспорт: netto={netto}, brutto={brutto}',
                metric_name='passport_errors',
            )
        else:
            post_settings = check_settings(post_number)
            if not post_settings.available:
                record_post_error(
                    post_number,
                    request_type,
                    'settings_missing',
                    'Настройки карусели отсутствуют',
                    metric_name='settings_errors',
                )
            elif not post_settings.read_only:
                weight_is_valid = True

                if not is_value_in_range(
                    netto,
                    post_settings.min_balloon_weight_from,
                    post_settings.min_balloon_weight_to,
                ):
                    weight_is_valid = False
                    record_post_error(
                        post_number,
                        request_type,
                        'weight_out_of_range',
                        'Паспортный вес netto вне диапазона: '
                        f'netto={netto}, '
                        f'от={post_settings.min_balloon_weight_from}, '
                        f'до={post_settings.min_balloon_weight_to}',
                        metric_name='weight_rejections',
                    )

                if not is_value_in_range(
                    brutto,
                    post_settings.max_balloon_weight_from,
                    post_settings.max_balloon_weight_to,
                ):
                    weight_is_valid = False
                    record_post_error(
                        post_number,
                        request_type,
                        'weight_out_of_range',
                        'Паспортный вес brutto вне диапазона: '
                        f'brutto={brutto}, '
                        f'от={post_settings.max_balloon_weight_from}, '
                        f'до={post_settings.max_balloon_weight_to}',
                        metric_name='weight_rejections',
                    )

                passport_diff = abs(brutto - netto)
                if (
                    post_settings.passport_weight_diff_from is None
                    or post_settings.passport_weight_diff_to is None
                ):
                    weight_is_valid = False
                    record_post_error(
                        post_number,
                        request_type,
                        'invalid_settings',
                        'Не задан диапазон разницы паспортных весов',
                        metric_name='settings_errors',
                    )
                elif not is_value_in_range(
                    passport_diff,
                    post_settings.passport_weight_diff_from,
                    post_settings.passport_weight_diff_to,
                ):
                    weight_is_valid = False
                    record_post_error(
                        post_number,
                        request_type,
                        'passport_weight_diff',
                        'Разница brutto/netto вне диапазона: '
                        f'diff={passport_diff}, '
                        f'от={post_settings.passport_weight_diff_from}, '
                        f'до={post_settings.passport_weight_diff_to}',
                        metric_name='weight_rejections',
                    )

                if post_settings.weight_correction is None:
                    weight_is_valid = False
                    record_post_error(
                        post_number,
                        request_type,
                        'invalid_post_correction',
                        'Не задан корректор веса для поста',
                        metric_name='settings_errors',
                    )

                if weight_is_valid:
                    response_required = True
                    full_weight = int(
                        (brutto + post_settings.weight_correction) * 1000
                    )
                    logger.debug(
                        f"Полный вес по паспорту: {brutto} кг. "
                        f"Коррекция: {post_settings.weight_correction} кг"
                    )

        process_data_to_server.update({
            'is_empty': True,
            'empty_weight': weight / 1000,
            'nfc_tag': balloon_from_cache.get("nfc_tag"),
            'serial_number': balloon_from_cache.get("serial_number"),
            'netto': balloon_from_cache.get("netto"),
            'brutto': balloon_from_cache.get("brutto"),
            'filling_status': balloon_from_cache.get("filling_status"),
        })

    elif request_type == '0x70':
        process_data_to_server['full_weight'] = weight / 1000
    else:
        record_post_error(
            post_number,
            request_type,
            'unknown_request_type',
            f'Неизвестный тип запроса {request_type}',
        )

    return response_required, full_weight, process_data_to_server


def serial_exchange(
    *,
    announce_start: bool = True,
    on_connected=None,
) -> None:
    """
    Обработка данных с постов наполнения баллонов.

    Каждый пост отправляет FRAME_SIZE байт, после чего ждёт ответ.
    Транспорт: TCP к NPort в режиме TCP Server.
    """
    transport: TcpTransport | None = None
    try:
        if announce_start:
            logger.info("Запуск программы обработки УНБ...")
        transport = open_transport()
        logger.info("Соединение с постами установлено.")
        if on_connected is not None:
            on_connected()

        last_wait_log_at = time.monotonic()

        while True:
            data = transport.read_frame(FRAME_SIZE)

            if len(data) == FRAME_SIZE:
                last_wait_log_at = time.monotonic()
                logger.info(f"Получен запрос от поста - {data}")
                request_type = data[0]
                post_number = data[1]
                service_byte = data[2]
                weight_combined = (data[3] << 8) | data[4]
                fill_flag = data[5]
                request_type_in_str = hex(request_type)

                crc_is_valid, received_crc, calculated_crc = (
                    validate_frame_crc(data)
                )
                if not crc_is_valid:
                    record_post_error(
                        post_number,
                        request_type_in_str,
                        'invalid_crc',
                        f'Кадр={data.hex().upper()}, '
                        f'получен CRC={received_crc:04X}, '
                        f'рассчитан CRC={calculated_crc:04X}',
                        metric_name='crc_errors',
                    )
                    continue

                logger.info(
                    f"Парсинг: тип={request_type_in_str}, "
                    f"пост={post_number}, служебный байт={service_byte:02X}, "
                    f"масса={weight_combined}, флаг={fill_flag:02X}"
                )

                is_duplicate, cached_response = get_cached_request(
                    request_type_in_str,
                    post_number,
                    weight_combined,
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
                        request_type_in_str,
                        post_number,
                        weight_combined,
                    )
                )

                response_packet = None
                if response_required:
                    response_packet = build_response_packet(
                        request_type,
                        post_number,
                        full_weight,
                    )

                cache_request_result(
                    request_type_in_str,
                    post_number,
                    weight_combined,
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
            else:
                now = time.monotonic()
                if now - last_wait_log_at >= WAIT_DATA_LOG_INTERVAL_SECONDS:
                    logger.info(
                        "Ожидание данных с постов (соединение активно)...",
                    )
                    last_wait_log_at = now

    finally:
        if transport is not None:
            transport.close()
            logger.debug("Соединение закрыто")


def main():
    last_transport_error: str | None = None
    repeat_count = 0

    def mark_connected() -> None:
        nonlocal last_transport_error, repeat_count
        last_transport_error = None
        repeat_count = 0

    while True:
        try:
            serial_exchange(
                announce_start=last_transport_error is None,
                on_connected=mark_connected,
            )
        except RECONNECTABLE_ERRORS as error:
            error_text = str(error)
            if error_text != last_transport_error:
                logger.error(
                    "Ошибка TCP-соединения: %s. "
                    "Повторное подключение через %s с.",
                    error,
                    RECONNECT_DELAY_SECONDS,
                )
                last_transport_error = error_text
                repeat_count = 1
            else:
                repeat_count += 1
                logger.debug(
                    "Повтор ошибки транспорта (раз подряд: %s). "
                    "Повторное подключение через %s с.",
                    repeat_count,
                    RECONNECT_DELAY_SECONDS,
                )
            time.sleep(RECONNECT_DELAY_SECONDS)
        except Exception as error:
            last_transport_error = None
            repeat_count = 0
            logger.error(
                "Ошибка в serial_exchange: %s. Перезапуск через %s с...",
                error,
                FATAL_RESTART_DELAY_SECONDS,
            )
            time.sleep(FATAL_RESTART_DELAY_SECONDS)


if __name__ == '__main__':
    main()
