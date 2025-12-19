import os
import asyncio
import struct
import logging
from typing import List, Dict
from asgiref.sync import sync_to_async
import django
from django.conf import settings
from concurrent.futures import ThreadPoolExecutor

# Инициализация Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'GNS.settings')
django.setup()

# Конфигурация логирования из настроек Django
logging.config.dictConfig(settings.LOGGING)
logger = logging.getLogger('rfid')

# Импорты из модулей
from .models import Reader, FeigProtocol

# Импорт моделей Django
from filling_station.models import ReaderSettings
# Импорт сервисов для прямого вызова
from filling_station import services


async def process_balloon_data_direct(nfc_tag, reader_number):
    """
    Прямой вызов сервисов для обработки данных баллона (без HTTP/Celery).
    """
    try:
        logger.debug(f'Прямая обработка RFID данных: nfc_tag={nfc_tag}, reader_number={reader_number}')

        if nfc_tag is None:
            # Обработка сигнала без NFC (оптический датчик)
            reader = services.processing_request_without_nfc(reader_number)
            if reader:
                logger.debug(f'Баллон без NFC обработан на ридере {reader_number}')
                return {'status': 'success', 'message': 'Баллон без NFC обработан'}
            else:
                logger.error(f'Ошибка обработки баллона без NFC на ридере {reader_number}')
                return {'status': 'error', 'message': 'Ошибка обработки баллона без NFC'}

        else:
            # Обработка сигнала с NFC меткой
            result = services.processing_request_with_nfc(nfc_tag=nfc_tag, reader_number=reader_number)
            if result:
                balloon, reader = result
                logger.debug(f'Баллон {balloon.nfc_tag} обработан на ридере {reader.number}')
                return {
                    'status': 'success',
                    'message': f'Баллон {balloon.nfc_tag} обработан',
                    'filling_status': balloon.filling_status
                }
            else:
                logger.error(f'Ошибка обработки баллона {nfc_tag} на ридере {reader_number}')
                return {'status': 'error', 'message': f'Ошибка обработки баллона {nfc_tag}'}

    except Exception as error:
        logger.error(f'Ошибка в process_balloon_data_direct: {error}')
        return {'error': str(error)}


async def data_exchange_with_reader(reader: Reader, command_name: str, request_data: bytes = b'') -> Dict:
    """
    Выполняет обмен данными со считывателем FEIG.
    """
    reader_conn, writer = await asyncio.open_connection(reader.ip, reader.port)
    try:
        # Создаем запрос согласно протоколу
        request = FeigProtocol.create_request(command_name, request_data)
        logger.debug(f'Отправляем запрос на {reader.ip}. request: {request.hex()}')
        writer.write(request)
        await writer.drain()

        header = await asyncio.wait_for(reader_conn.read(5), timeout=1)
        if len(header) < 5:
            logger.error(f'Неполный заголовок {reader.ip}')
            return {'error': 'Incomplete header', 'valid': False}

        # Получаем длину полного ответа
        length = struct.unpack('>H', header[1:3])[0]

        # Читаем оставшуюся часть пакета
        remaining = length - 5
        if remaining > 0:
            body = await asyncio.wait_for(reader_conn.read(remaining), timeout=1)
            response = header + body
        else:
            response = header

        # Парсим ответ
        parsed = FeigProtocol.parse_response(response)

        if not parsed.get('valid'):
            logger.error(f'Невалидный ответ от {reader.ip}: {parsed.get("error")}')

        return parsed

    except asyncio.TimeoutError:
        logger.error(f'Таймаут при ожидании ответа от {reader.ip}:{reader.port}')
        return {'error': 'Timeout', 'valid': False}
    except Exception as error:
        logger.error(f'Нет связи с {reader.ip}:{reader.port}: {error}')
        return {'error': str(error), 'valid': False}
    finally:
        writer.close()
        await writer.wait_closed()


async def read_nfc_tags(reader: Reader):
    """
    Чтение всех меток из буфера ридера. Возвращает список уникальных меток.
    """
    # MODE = 0x00, DATA-SETS = 0xFFFF (читать все доступные)
    request_data = bytes([0x00,0xff,0xff])  # MODE + DATA-SETS

    response = await data_exchange_with_reader(reader, 'READ_BUFFER', request_data)

    tags = []
    if response.get('valid'):
        # Парсим данные буфера
        tags_data = FeigProtocol.parse_buffer_data(response.get('response_data'))
        logger.debug(f'Данные с {reader} валидны. '
                     f'Команда {tags_data[0].get("nfc_tag")}. '
                     f'Статус {tags_data[0].get("status")}')

        for tag_data in tags_data:
            if (nfc_tag := tag_data.get('nfc_tag')) and reader.filter_duplicate_tag(nfc_tag):
                tags.append(nfc_tag)

    logger.debug(f'Список меток с {reader} - {tags}')
    return tags


async def read_input_status(reader: Reader) -> int:
    """
    Чтение состояния входов ридера (команда GET_INPUT). Возвращает состояние первого входа (IN1).
    """
    response = await data_exchange_with_reader(reader, 'GET_INPUT')

    if response.get('valid'):
        logger.debug(f'Данные с ридера {reader} по входам валидны. Обработка буфера')
        inputs_state = FeigProtocol.parse_buffer_data(response.get('response_data'))
        logger.debug(f'Данные с {reader} валидны. '
                     f'Команда {inputs_state[0].get("nfc_tag")}. '
                     f'Статус {inputs_state[0].get("status")}')

        return inputs_state[1].get('IN1')

    return reader.input_state  # Возвращаем предыдущее состояние при ошибке


async def process_reader_operations(reader: Reader):
    """
    Основная функция обработки операций ридера.
    """
    while True:
        try:
            # 1. Проверяем состояние входов
            current_input_state = await read_input_status(reader)

            # Если состояние изменилось с 0 на 1 (передний фронт)
            if current_input_state == 1 and reader.input_state == 0:
                # Прямой вызов сервиса вместо HTTP/Celery
                await process_balloon_data_direct(nfc_tag=None, reader_number=reader.number)
                logger.debug(f'Сработал вход на {reader}')

            # Обновляем состояние входа
            reader.input_state = current_input_state

            # 2. Читаем метки из буфера
            tags = await read_nfc_tags(reader)

            for nfc_tag in tags:
                try:
                    # Прямой вызов сервиса для обработки NFC метки
                    result = await process_balloon_data_direct(nfc_tag=nfc_tag, reader_number=reader.number)

                    # Управление светодиодами ридера на основе результата
                    if result.get('filling_status') == True:
                        # Зажигаем зелёную лампу
                        await data_exchange_with_reader(reader, 'SET_OUTPUT', b'\x01\x01\x81\x01\x00')
                    else:
                        # Мигание зелёной лампы
                        await data_exchange_with_reader(reader, 'SET_OUTPUT', b'\x01\x01\x81\x0B\x00')

                except Exception as error:
                    logger.error(f'Ошибка обработки метки {nfc_tag} на {reader.ip}: {error}')

            # 3. Очищаем буфер (только прочитанные записи)
            if tags:
                logger.debug(f'Очистка буфера считанных меток на {reader}')
                await data_exchange_with_reader(reader, 'CLEAR_BUFFER')

            # Небольшая задержка перед следующей итерацией
            await asyncio.sleep(0.3)

        except Exception as error:
            logger.error(f"Ошибка в process_reader_operations для ридера {reader.ip}: {error}")
            await asyncio.sleep(1)  # Пауза при ошибке


async def initialize_readers(readers: List[Reader]):
    """
    Инициализация ридеров при запуске.
    """
    tasks = []
    for reader in readers:
        # Очищаем буфер при запуске
        task = asyncio.create_task(data_exchange_with_reader(reader, 'INITIALIZE_BUFFER'))
        tasks.append(task)

    logger.info('Инициализация RFID-считывателей...')
    await asyncio.gather(*tasks)


def process_reader_sync(reader: Reader):
    """Синхронная обертка для запуска в ThreadPoolExecutor"""
    asyncio.run(process_reader_operations(reader))


async def load_readers_from_database():
    """
    Загрузка конфигурации ридеров из базы данных Django.
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
    logger.info('Запуск программы считывания RFID-меток (прямой вызов сервисов)...')

    # Загрузка ридеров из базы данных
    readers = await load_readers_from_database()

    if not readers:
        logger.error('Не удалось загрузить конфигурацию ридеров. Завершение работы.')
        return

    # Инициализация ридеров
    await initialize_readers(readers)

    # Запуск обработки для каждого ридера
    with ThreadPoolExecutor(max_workers=len(readers)) as executor:
        logger.info('Программа в работе')
        loop = asyncio.get_running_loop()
        tasks = [
            loop.run_in_executor(executor, process_reader_sync, reader)
            for reader in readers
        ]
        await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
