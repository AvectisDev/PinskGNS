import os
import asyncio
import logging
import logging.config
import struct
from typing import List, Dict
from asgiref.sync import sync_to_async
import django
from django.conf import settings

# Инициализация Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'GNS.settings')
django.setup()

# Логирование
logging.config.dictConfig(settings.LOGGING)
logger = logging.getLogger('rfid')

# Импорт моделей/протокола и ReaderSession
from .models import Reader, FeigProtocol, ReaderSession
# Импорт моделей Django
from filling_station.models import ReaderSettings
# Импорт сервисов (синхронные)
from filling_station import services

NOTIFICATION_LISTEN_HOST = os.getenv('RFID_NOTIFICATION_LISTEN_HOST', '0.0.0.0')
NOTIFICATION_LISTEN_PORT = int(os.getenv('RFID_NOTIFICATION_LISTEN_PORT', '8002'))
# UID баллонов в проекте — hex-строка, оканчивающаяся на этот суффикс (например ...1be0).
TAG_HEX_SUFFIX = os.getenv('RFID_TAG_HEX_SUFFIX', 'e0').strip().lower()


def is_balloon_nfc_tag(nfc_tag: str) -> bool:
    """
    True, если метка похожа на ожидаемый UID баллона: корректный hex и суффикс TAG_HEX_SUFFIX.
    Иные значения (шум, чужие транспондеры) логируются и не идут в бизнес-логику.
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


@sync_to_async
def process_balloon_data_sync(nfc_tag, reader_number):
    """
    Прямой вызов сервисов (синхронных) в отдельном потоке через asgiref.sync_to_async,
    чтобы не блокировать event-loop.
    """
    if nfc_tag is None:
        reader = services.processing_request_without_nfc(reader_number)
        if reader:
            return {'status': 'success',
                    'message': f'Баллон без NFC обработан на ридере {reader_number}'}
        return {'status': 'error',
                'message': f'Ошибка обработки баллона без NFC на ридере {reader_number}'}
    else:
        result = services.processing_request_with_nfc(nfc_tag=nfc_tag, reader_number=reader_number)
        if result:
            balloon, reader = result
            # Отправка статуса в Мириаду
            if reader.number in [3, 4, 6, 8]:
                services.send_status_to_miriada(reader=reader.number, nfc_tag=balloon.nfc_tag)
            return {
                'status': 'success',
                'message': f'Баллон {balloon.nfc_tag} обработан на ридере {reader_number}',
                'filling_status': balloon.filling_status
            }
        return {'status': 'error',
                'message': f'Ошибка обработки баллона {nfc_tag} на ридере {reader_number}'}


async def read_frame(reader_stream: asyncio.StreamReader) -> bytes:
    header = await reader_stream.readexactly(3)
    if header[0] != FeigProtocol.STX:
        raise ValueError(f'Invalid STX byte: 0x{header[0]:02X}')
    frame_len = struct.unpack('>H', header[1:3])[0]
    if frame_len < 7:
        raise ValueError(f'Invalid FEIG frame length: {frame_len}')
    body = await reader_stream.readexactly(frame_len - 3)
    return header + body


def get_peer_ip(writer: asyncio.StreamWriter) -> str:
    peer = writer.get_extra_info('peername')
    if isinstance(peer, tuple) and peer:
        return str(peer[0])
    return 'unknown'


async def send_notification_ack(writer: asyncio.StreamWriter, command: int, status: int = 0x00):
    ack = FeigProtocol.create_request_by_code(command, bytes([status]))
    writer.write(ack)
    await writer.drain()


async def process_tag_event(
    reader_obj: Reader,
    command_session: ReaderSession,
    parsed_records: List[Dict],
) -> None:
    tags: List[str] = []
    for tag_data in parsed_records[1:]:
        nfc_tag = tag_data.get('nfc_tag') if isinstance(tag_data, dict) else None
        if not nfc_tag:
            continue
        if not is_balloon_nfc_tag(nfc_tag):
            logger.info(
                f'{reader_obj.number} Метка {nfc_tag} не проходит фильтр UID (suffix={TAG_HEX_SUFFIX!r})'
            )
            continue
        if reader_obj.filter_duplicate_tag(nfc_tag):
            tags.append(nfc_tag)

    if tags:
        logger.info(f'{reader_obj.number} Получены метки из Notification Mode: {tags}')

    for nfc_tag in tags:
        result = await process_balloon_data_sync(nfc_tag=nfc_tag, reader_number=reader_obj.number)
        if result.get('filling_status'):
            await command_session.send('SET_OUTPUT', b'\x01\x01\x81\x01\x00')  # зелёный
        else:
            await command_session.send('SET_OUTPUT', b'\x01\x01\x81\x0B\x00')  # мигание


async def process_input_event(reader_obj: Reader, parsed_records: List[Dict]) -> None:
    logger.info(f'{reader_obj.number} Получен Input Event (0x2C), records={len(parsed_records) - 1}')
    for event_data in parsed_records[1:]:
        if not isinstance(event_data, dict):
            logger.warning(f'{reader_obj.number} Input Event record не dict: {event_data!r}')
            continue
        in1_previous = bool(event_data.get('IN1_previous', False))
        in1_current = bool(event_data.get('IN1_current', False))
        in2_previous = bool(event_data.get('IN2_previous', False))
        in2_current = bool(event_data.get('IN2_current', False))
        in3_previous = bool(event_data.get('IN3_previous', False))
        in3_current = bool(event_data.get('IN3_current', False))

        logger.info(
            f'{reader_obj.number} Input Event states: '
            f'IN1 {int(in1_previous)}->{int(in1_current)}, '
            f'IN2 {int(in2_previous)}->{int(in2_current)}, '
            f'IN3 {int(in3_previous)}->{int(in3_current)}'
        )
        if in1_current and not in1_previous:
            await process_balloon_data_sync(nfc_tag=None, reader_number=reader_obj.number)
            logger.info(f'{reader_obj.number} Сработал вход IN1 (Notification Mode)')
        reader_obj.input_state = int(in1_current)


async def process_notification_payload(
    reader_obj: Reader,
    command_session: ReaderSession,
    payload: bytes,
) -> int:
    logger.debug(f'{reader_obj.number} Event payload: {payload.hex()}')
    parsed = FeigProtocol.parse_buffer_data(payload)
    if not parsed:
        logger.warning(f'{reader_obj.number} Пустой payload события')
        return 0x81

    command = parsed[0].get('command')
    status = parsed[0].get('status')
    logger.info(f'{reader_obj.number} Notification Event 0x{command:02X} status={status}')
    if command == 0x2A:
        logger.debug(f'{reader_obj.number} Получен Reader Identification / Heartbeat')
        return 0x00
    if command == 0x2B:
        await process_tag_event(reader_obj, command_session, parsed)
        return 0x00
    if command == 0x2C:
        logger.debug(f'{reader_obj.number} Parsed Input Event records: {parsed[1:]}')
        await process_input_event(reader_obj, parsed)
        return 0x00

    logger.warning(f'{reader_obj.number} Неподдерживаемый Notification Event 0x{command:02X}')
    return 0x80


async def initialize_command_sessions(readers: List[Reader]) -> Dict[int, ReaderSession]:
    sessions: Dict[int, ReaderSession] = {}
    for reader in readers:
        sessions[reader.number] = ReaderSession(reader)

    logger.info('Открытие управляющих TCP-сессий к RFID-ридерам...')
    connect_tasks = [sessions[reader.number].connect() for reader in readers]
    results = await asyncio.gather(*connect_tasks, return_exceptions=True)
    for reader, result in zip(readers, results):
        if isinstance(result, Exception):
            logger.warning(f'{reader.number} Не удалось открыть управляющую сессию: {result}')
    return sessions


async def handle_notification_connection(
    stream_reader: asyncio.StreamReader,
    stream_writer: asyncio.StreamWriter,
    readers_by_ip: Dict[str, Reader],
    sessions: Dict[int, ReaderSession],
):
    peer_ip = get_peer_ip(stream_writer)
    reader_obj = readers_by_ip.get(peer_ip)

    if reader_obj is None:
        logger.warning(f'Подключение от неизвестного ридера: {peer_ip}')
    else:
        logger.info(f'Notification connection от ридера {reader_obj.number} ({peer_ip})')

    try:
        while True:
            frame = await read_frame(stream_reader)
            parsed_response = FeigProtocol.parse_response(frame)
            if not parsed_response.get('valid'):
                logger.warning(f'Невалидный кадр от {peer_ip}: {parsed_response.get("error")}')
                break

            payload = parsed_response.get('response_data', b'')
            if len(payload) < 1:
                logger.warning(f'Пустой response_data от {peer_ip}')
                break

            event_command = payload[0]
            ack_status = 0x00

            logger.debug(f'Event from {peer_ip}: cmd=0x{event_command:02X} frame={frame.hex()}')

            if reader_obj is not None and reader_obj.number in sessions:
                try:
                    ack_status = await process_notification_payload(
                        reader_obj=reader_obj,
                        command_session=sessions[reader_obj.number],
                        payload=payload,
                    )
                except Exception as error:
                    logger.error(f'{reader_obj.number} Ошибка обработки события 0x{event_command:02X}: {error}')
                    ack_status = 0x01
            else:
                ack_status = 0x04

            await send_notification_ack(stream_writer, event_command, ack_status)

    except asyncio.IncompleteReadError:
        pass
    except Exception as error:
        logger.error(f'Ошибка Notification connection ({peer_ip}): {error}')
    finally:
        stream_writer.close()
        await stream_writer.wait_closed()
        if reader_obj is not None:
            logger.info(f'Notification connection закрыт для ридера {reader_obj.number} ({peer_ip})')
        else:
            logger.info(f'Notification connection закрыт ({peer_ip})')


async def load_readers_from_database() -> List[Reader]:
    """
    Загрузка конфигурации ридеров из БД
    """
    readers = []

    @sync_to_async
    def get_readers_from_db():
        return list(ReaderSettings.objects.all())

    try:
        reader_settings_list = await get_readers_from_db()
        for reader_settings in reader_settings_list:
            reader = Reader(reader_settings)
            readers.append(reader)
            logger.info(f'Загружен ридер {reader}')
    except Exception as error:
        logger.error(f'Ошибка при загрузке ридеров из базы данных: {error}')

    return readers


async def main():
    """
    Точка входа Notification Mode:
    сервер слушает TCP-порт и принимает события от ридеров.
    """
    logger.info('Запуск Notification Mode сервера RFID...')
    readers = await load_readers_from_database()
    if not readers:
        logger.error('Не удалось загрузить конфигурацию ридеров. Завершение работы.')
        return

    readers_by_ip: Dict[str, Reader] = {reader.ip: reader for reader in readers if reader.ip}
    sessions = await initialize_command_sessions(readers)

    async def _handler(reader_stream: asyncio.StreamReader, writer_stream: asyncio.StreamWriter):
        await handle_notification_connection(
            stream_reader=reader_stream,
            stream_writer=writer_stream,
            readers_by_ip=readers_by_ip,
            sessions=sessions,
        )

    server = await asyncio.start_server(_handler, host=NOTIFICATION_LISTEN_HOST, port=NOTIFICATION_LISTEN_PORT)
    sockets = server.sockets or []
    socket_info = ', '.join(f'{sock.getsockname()}' for sock in sockets)
    logger.info(f'Notification listener запущен: {socket_info}')

    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
