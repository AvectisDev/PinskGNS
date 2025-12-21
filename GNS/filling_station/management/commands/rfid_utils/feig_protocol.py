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
# Импорт Celery задач
from filling_station.tasks import process_rfid_balloon_data


async def data_exchange_with_reader(reader: Reader, command_name: str, request_data: bytes = b'') -> Dict:
    """
    Выполняет обмен данными со считывателем FEIG.
    """
    reader_conn, writer = await asyncio.open_connection(reader.ip, reader.port)
    try:
        # Создаем запрос согласно протоколу
        request = FeigProtocol.create_request(command_name, request_data)
        logger.debug(f'{reader.number} Отправляем запрос: {request.hex()}')
        writer.write(request)
        await writer.drain()

        response = await asyncio.wait_for(reader_conn.read(4096), timeout=1)

        # Парсим ответ
        parsed = FeigProtocol.parse_response(response)

        if not parsed.get('valid'):
            logger.error(f'{reader.number} Невалидный ответ: {parsed.get("error")}')

        return parsed

    except asyncio.TimeoutError:
        logger.error(f'{reader.number} Таймаут при ожидании ответа')
        return {'error': 'Timeout', 'valid': False}
    except Exception as error:
        logger.error(f'{reader.number} Нет связи. {error}')
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
        logger.debug(f'{reader} Данные валидны. '
                     f'Команда {tags_data[0].get("command")}. '
                     f'Статус {tags_data[0].get("status")}')

        for tag_data in tags_data:
            if (nfc_tag := tag_data.get('nfc_tag')) and reader.filter_duplicate_tag(nfc_tag):
                tags.append(nfc_tag)

    logger.debug(f'{reader} Список меток {tags}')
    return tags


async def read_input_status(reader: Reader) -> int:
    """
    Чтение состояния входов ридера (команда GET_INPUT). Возвращает состояние первого входа (IN1).
    """
    response = await data_exchange_with_reader(reader, 'GET_INPUT')

    if response.get('valid'):
        inputs_state = FeigProtocol.parse_buffer_data(response.get('response_data'))
        logger.debug(f'{reader} Данные валидны. '
                     f'Команда {inputs_state[0].get("command")}. '
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
                # Отправляем задачу в Celery для обработки сигнала без NFC
                process_rfid_balloon_data.delay(nfc_tag=None, reader_number=reader.number)
                logger.debug(f'{reader} Сработал вход')

            # Обновляем состояние входа
            reader.input_state = current_input_state

            # 2. Читаем метки из буфера
            tags = await read_nfc_tags(reader)

            for nfc_tag in tags:
                try:
                    # Отправляем задачу в Celery для обработки NFC метки
                    task_result = process_rfid_balloon_data.delay(nfc_tag=nfc_tag, reader_number=reader.number)
                    # Получаем результат задачи (синхронно, но можно сделать асинхронно)
                    # Для асинхронного получения результата можно использовать task_result.get(timeout=10)
                    logger.debug(f'{reader.number} Отправлена задача обработки NFC метки {nfc_tag}')

                    # Управление светодиодами ридера - пока оставим логику по умолчанию
                    # В будущем можно получить filling_status из результата задачи
                    await data_exchange_with_reader(reader, 'SET_OUTPUT', b'\x01\x01\x81\x01\x00')  # Зеленый

                except Exception as error:
                    logger.error(f'{reader.number} Ошибка обработки метки {nfc_tag}: {error}')

            # 3. Очищаем буфер (только прочитанные записи)
            if tags:
                logger.debug(f'{reader} Очистка буфера считанных меток')
                await data_exchange_with_reader(reader, 'CLEAR_BUFFER')

            # Небольшая задержка перед следующей итерацией
            await asyncio.sleep(0.3)

        except Exception as error:
            logger.error(f"{reader.number} Ошибка в process_reader_operations: {error}")
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
            logger.info(f'{reader} Загружен')

    except Exception as error:
        logger.error(f'Ошибка при загрузке ридеров из базы данных: {error}')

    return readers


async def main():
    logger.info('Запуск программы считывания RFID-меток...')

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
