import os
import asyncio
import logging
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
            if (2 <= reader.number <= 6) or reader.number == 8:
                services.send_status_to_miriada(reader=reader.number, nfc_tag=balloon.nfc_tag)
            return {
                'status': 'success',
                'message': f'Баллон {balloon.nfc_tag} обработан на ридере {reader_number}',
                'filling_status': balloon.filling_status
            }
        return {'status': 'error',
                'message': f'Ошибка обработки баллона {nfc_tag} на ридере {reader_number}'}


# -------------------------------
# Вспомогательные функции протокола FEIG
# -------------------------------
async def read_input_status(session: ReaderSession, reader: Reader) -> int:
    """
    Чтение состояния входов (GET_INPUT).
    Возвращает состояние IN1: 0/1.
    """
    response = await session.send('GET_INPUT')
    if response.get('valid'):
        inputs_state = FeigProtocol.parse_buffer_data(response.get('response_data'))
        logger.debug(f'{reader.number} Данные валидны. Команда {inputs_state[0].get("command")}. '
                     f'Статус {inputs_state[0].get("status")}')
        return int(inputs_state[1].get('IN1'))
    return reader.input_state  # при ошибке — предыдущий


async def read_buffer_info(session: ReaderSession, reader: Reader) -> int:
    """
    Чтение информации о буфере (READ_BUFFER_INFO).
    Возвращает количество доступных записей (>=0).
    """
    response = await session.send('READ_BUFFER_INFO')
    if response.get('valid'):
        info = FeigProtocol.parse_buffer_data(response.get('response_data'))
        logger.debug(f'{reader.number} Данные валидны. Команда {info[0].get("command")}. '
                     f'Статус {info[0].get("status")}')

        amount_of_data_sets = info[1].get("available")
        if amount_of_data_sets > 0:
            return True
    return False


async def read_nfc_tags(session: ReaderSession, reader: Reader) -> List[str]:
    """
    Чтение всех меток из буфера ридера (READ_BUFFER) — только если они есть.
    Возвращает список уникальных меток (отфильтрованных от повторов).
    """
    # MODE=0x00, DATA-SETS=0xFFFF (читать все доступные)
    request_data = bytes([0x00, 0xFF, 0xFF])
    response = await session.send('READ_BUFFER', request_data)

    tags = []
    if response.get('valid'):
        tags_data = FeigProtocol.parse_buffer_data(response.get('response_data'))
        logger.debug(f'{reader.number} Данные валидны. '
                     f'Команда {tags_data[0].get("command")}. '
                     f'Статус {tags_data[0].get("status")}')
        for tag_data in tags_data:
            nfc_tag = tag_data.get('nfc_tag')
            if nfc_tag and reader.filter_duplicate_tag(nfc_tag):
                tags.append(nfc_tag)
        if tags:
            logger.info(f'{reader.number} Список меток {tags}')
    return tags


async def process_reader_operations(reader: Reader, session: ReaderSession):
    """
    Основная функция обработки одного ридера:
    - фронт IN1 → событие «без NFC»
    - при наличии записей в буфере → чтение, обработка и очистка
    """
    timeouts = 0

    while True:
        try:
            # 1 - опрос входов
            current_input_state = await read_input_status(session, reader)
            if current_input_state == 1 and reader.input_state == 0:
                # фронт: отправляем событие без NFC
                await process_balloon_data_sync(nfc_tag=None, reader_number=reader.number)
                logger.info(f'{reader.number} Сработал вход IN1')
            reader.input_state = current_input_state

            # 2 - чтение буфера
            tags = await read_nfc_tags(session, reader)

            for nfc_tag in tags:
                try:
                    result = await process_balloon_data_sync(nfc_tag=nfc_tag, reader_number=reader.number)
                    # управление LED
                    if result.get('filling_status'):
                        await session.send('SET_OUTPUT', b'\x01\x01\x81\x01\x00')  # зелёный
                    else:
                        await session.send('SET_OUTPUT', b'\x01\x01\x81\x0B\x00')  # мигание
                except Exception as error:
                    logger.error(f'{reader.number} Ошибка обработки метки {nfc_tag}: {error}')

            # очистка буфера после чтения
            await session.send('CLEAR_BUFFER')

            # задержка между итерациями
            await asyncio.sleep(0.3)

            # сброс счётчика тайм-аутов при успешном круге
            timeouts = 0

        except asyncio.TimeoutError:
            # таймауты подряд → переподключение
            timeouts += 1
            if timeouts >= 3:
                logger.warning(f'{reader}: таймаутов подряд = {timeouts} , переподключение...')
                await session.close()
                await asyncio.sleep(0.5)
                await session.connect()
                timeouts = 0
            else:
                await asyncio.sleep(0.3)

        except Exception as error:
            logger.error(f"{reader.number} Ошибка в process_reader_operations: {error}")
            await asyncio.sleep(1)


async def initialize_readers(readers: List[Reader], sessions: Dict[int, ReaderSession]):
    """
    Инициализация ридеров (очистка буферов и старт постоянных TCP-сессий)
    """
    tasks = []
    for reader in readers:
        session = ReaderSession(reader)
        sessions[reader.number] = session
        tasks.append(session.connect())
    logger.info('Установка TCP-сессий к RFID-ридерам...')
    await asyncio.gather(*tasks)

    # на старте — полная очистка буферов
    init_tasks = [sessions[r.number].send('INITIALIZE_BUFFER') for r in readers]
    logger.info('Инициализация (полная очистка буферов)...')
    await asyncio.gather(*init_tasks)


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
    Точка входа: один event-loop, по задаче на ридер
    """
    logger.info('Запуск программы считывания RFID-меток...')
    readers = await load_readers_from_database()
    if not readers:
        logger.error('Не удалось загрузить конфигурацию ридеров. Завершение работы.')
        return

    sessions: Dict[int, ReaderSession] = {}
    await initialize_readers(readers, sessions)

    tasks = [asyncio.create_task(process_reader_operations(reader, sessions[reader.number]))
             for reader in readers]
    logger.info('Программа в работе')
    await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
