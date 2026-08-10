import os
import serial
import struct
import logging.config
import django
import time


# Инициализация Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'GNS.settings')
django.setup()

from django.core.cache import cache
from django.core.exceptions import ValidationError

from carousel.services import (
    CarouselPostNotFoundError,
    UnsupportedCarouselRequestError,
    get_carousel_settings_data,
    process_carousel_data_direct,
)

# Конфигурация логирования из настроек Django
logging.config.dictConfig(django.conf.settings.LOGGING)
logger = logging.getLogger('carousel')

# Ключи Django cache (Redis DB настраивается в settings.CACHES)
CACHE_KEY = 'reader_8_balloon_stack'
POST_NUMBER_CACHE_KEY = 'previous_post_number'

# Указываем порт и скорость соединения
PORT = 'COM3'
BAUD_RATE = 9600


def get_and_remove_last_balloon():
    """
    Извлекает последний элемент из стека баллонов в Redis и удаляет его. Работа со стеком по принципу FIFO
    """
    cache_timeout = 600
    balloons = cache.get(CACHE_KEY)

    if balloons:
        try:
            if isinstance(balloons, list) and balloons:
                last_item = balloons.pop()
                cache.set(CACHE_KEY, balloons, timeout=cache_timeout)
                return last_item
            else:
                logger.info("Кэш. Данные не являются списком или список пуст")
                return None
        except Exception as error:
            logger.error(f"Кэш. Ошибка при десериализации данных: {error}")
            return None
    return None


def put_carousel_data(data: dict) -> bool:
    """
    Сохраняет показания поста карусели напрямую через сервис Django.

    Пост передаёт данные через COM-порт в виде набора байт по
    проприетарному протоколу, поэтому COM-процесс преобразует их в словарь
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
        logger.error(f"Ошибка обработки данных с поста наполнения: {error}")
    except Exception as error:
        logger.exception(f"Ошибка сохранения данных с поста наполнения: {error}")
    return False


def calc_crc(message):
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


def post_processing(post_number: int):
    """
    контролирует порядок обработки постов. Запросы с постов идут в обратном порядке, например 2-1-20-19-18 и т.д.
    Если в определённый порядок вклинивается неверный пост, то такую обработку пропускаем.
    Используется только для типов запроса 0x7a (установка пустого баллона на пост).
    :param post_number: Номер текущего поста наполнения
    :return: bool: указывает нужно ли обрабатывать текущий запрос на наполнение
    """
    cache_timeout = 5
    previous_post_number = cache.get(POST_NUMBER_CACHE_KEY)
    logger.debug(f"Последний номер поста в кеше - {previous_post_number}.")

    if previous_post_number:
        process_value = int(previous_post_number) - post_number
        logger.debug(f"Значение process_value = {process_value}")

        # if process_value in [0, 1, -19]:  # также разрешается повторный запрос с поста - значение 0
        if process_value:
            cache.set(POST_NUMBER_CACHE_KEY, post_number, timeout=cache_timeout)
            logger.debug(f"Значение {post_number} сохранено в Redis по ключу {POST_NUMBER_CACHE_KEY}")
            return True
        else:
            return False
    else:
        # Если в кеше нет данных, значит это первая обработка функции
        cache.set(POST_NUMBER_CACHE_KEY, post_number, timeout=cache_timeout)
        logger.debug(f"Значение {post_number} сохранено в Redis по ключу {POST_NUMBER_CACHE_KEY}")
        return True


def check_settings(post_number: int):
    """
    проверяет настройки обработки постов в базе данных. Если установлено только чтение, то на пост не должны
    передаваться данные. Если установлена корректировка веса, то вес на пост должен быть отправлен с учётом корректировки
    :param post_number: Номер текущего поста наполнения
    :return: tuple: Кортеж со значениями - Нужна ли передача веса на пост и параметр коррекции веса
    """
    # Значения по умолчанию
    weight_correction_value = 0.0
    transmit_command = False

    post_settings = get_carousel_settings_data()

    if post_settings:
        logger.debug(f'Настройки поста наполнения {post_settings}')
        
        if post_settings.get('read_only'):
            return (
                transmit_command,
                weight_correction_value,
                post_settings.get('min_balloon_weight'),
                post_settings.get('max_balloon_weight'),
                post_settings.get('max_passport_weight_diff'),
            )

        transmit_command = True
        logger.debug(f'Требуется отправка веса на пост {post_number}')
        if post_settings.get('use_weight_management'):
            if post_settings.get('use_common_correction'):
                weight_correction_value = post_settings.get('weight_correction_value')
            else:
                weight_correction_value = post_settings.get(f'post_{post_number}_correction')
        logger.debug(f'Требуется отправка веса на пост. weight_correction_value = {post_settings}')

    if not post_settings:
        post_settings = {}

    return (
        transmit_command,
        weight_correction_value,
        post_settings.get('min_balloon_weight'),
        post_settings.get('max_balloon_weight'),
        post_settings.get('max_passport_weight_diff'),
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


def request_caching(request_type: str, post_number: int, weight: int) -> bool:
    """
    кеширует запрос от поста наполнения.
    :param weight: Вес баллона перед наполнением
    :return: bool: требуется обработка запроса
    """
    request_processing_required = True
    cache_key = f"carousel_request_{request_type}_{post_number}_{weight}"
    cache_time = 1

    if not cache.add(cache_key, "1", timeout=cache_time):
        request_processing_required = False
        logger.debug(f"Запрос с ключём {cache_key} уже обрабатывается")
        return request_processing_required

    return request_processing_required


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
        'carousel_number': 1,
        'request_type': request_type,
        'post_number': post_number,
        'size': check_balloon_size(weight)
    }

    if request_type == '0x7a':
        logger.debug(f"Запрос 0x7a")

        if not post_processing(post_number):
            logger.debug("Пост не прошел проверку очередности")
            return response_required, full_weight, {'error': 'post_order_failed'}

        # Забираем данные по баллону из кэша
        balloon_from_cache = get_and_remove_last_balloon()

        if not balloon_from_cache:
            logger.debug("Нет данных по баллону в кеше")
            process_data_to_server.update({
                'is_empty': True,
                'empty_weight': weight / 1000
            })
            return response_required, full_weight, process_data_to_server

        # Обработка данных баллона
        if balloon_from_cache.get('filling_status') and (brutto := balloon_from_cache.get('brutto')):
            response_required, weight_correction, min_balloon_weight, max_balloon_weight, max_passport_weight_diff = check_settings(post_number)
            
            netto = balloon_from_cache.get('netto')

            if (
                (min_balloon_weight is not None and netto is not None and netto < min_balloon_weight) or
                (max_balloon_weight is not None and brutto > max_balloon_weight)
            ):
                response_required = False
                logger.debug("Вес баллона не входит в допустимый диапазон")

            passport_diff = abs(brutto - netto)
            if passport_diff > max_passport_weight_diff:
                response_required = False
                logger.debug(f"Разница между паспортными весами превышает допустимое значение: {passport_diff} > {max_passport_weight_diff}")

            if response_required:
                full_weight = int((brutto + weight_correction) * 1000)
                logger.debug(f"Требуется отправка веса на пост. Полный вес баллона по паспорту: {brutto} кг. "
                             f"Коррекция веса: {weight_correction} кг")

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

    return response_required, full_weight, process_data_to_server


def serial_exchange():
    """
    Функция обработки данных с поста наполнения баллонов. Каждый пост отправляет 8 байт данных, после чего ждёт ответ.
    В зависимости от типа запроса в ответе должен быть либо вес баллона, либо ответ не нужен.
    :return:
    """
    ser = None
    try:
        logger.info(f"Запуск программы обработки УНБ...")
        # Создаем объект Serial для работы с COM-портом
        ser = serial.Serial(PORT, BAUD_RATE, timeout=1)
        logger.info(f"Соединение установлено на порту {PORT}.")

        while True:
            data = ser.read(8)

            if len(data) == 8:
                logger.info(f"Получен запрос от поста - {data}")
                request_type = data[0]
                post_number = data[1]
                measurement_number = data[2]
                # Преобразуем четвертый и пятый байты в десятичное значение массы баллона
                weight_combined = (data[3] << 8) | data[4]
                service_byte = int.from_bytes(data[5:7], byteorder='little')
                crc = int.from_bytes(data[6:8], byteorder='little')

                request_type_in_str = str(hex(request_type))
                logger.info(f"Парсинг: Тип запроса: {request_type_in_str}. "
                             f"Номер поста: {post_number}. Масса баллона: {weight_combined}")

                # Обработка запроса с поста
                if request_caching(request_type_in_str, post_number, weight_combined):
                    response_required, full_weight, process_data_to_server = request_processing(
                        request_type_in_str,
                        post_number,
                        weight_combined
                    )

                    if response_required:
                        # Формируем ответ
                        if request_type == 0x7A:
                            response_type = 0x5A
                        elif request_type == 0x70:
                            response_type = 0x50

                        # Меняем порядок байтов для full_weight
                        full_weight_bytes = struct.pack('>H', full_weight)  # Упаковываем в big-endian
                        full_weight_reversed = int.from_bytes(full_weight_bytes, 'little')  # Меняем порядок байтов

                        # Формируем ответный пакет без CRC
                        response_data = struct.pack('<BBBHBH',
                                                    response_type,
                                                    post_number,
                                                    0xFF,
                                                    full_weight_reversed,
                                                    0xFF,
                                                    0xFFFF)

                        # Вычисляем CRC-16/AUG-CCITT для ответа (без последних двух байт)
                        crc_t = calc_crc(response_data[:-2])
                        crc = ((crc_t & 0xFF) << 8) | ((crc_t >> 8) & 0xFF)

                        response_with_crc = response_data[:-2] + struct.pack('<H', crc)

                        ser.write(response_with_crc)
                        logger.debug(f"Отправлен ответ на пост: {response_with_crc.hex().upper()}")

                    # Отправляем данные на сервер для статистики
                    if process_data_to_server and isinstance(process_data_to_server, dict):
                        put_carousel_data(process_data_to_server)

    except serial.SerialException as error:
        logger.error(f"Ошибка: {error}. Проверьте правильность указанного порта.")
    except Exception as error:
        logger.error(f"Общая ошибка: {error}.")
    finally:
        if ser:
            # Закрываем соединение только если оно было открыто
            ser.close()
            logger.debug("Соединение закрыто")


def main():
    while True:
        try:
            serial_exchange()
        except Exception as error:
            logger.error(
                f"Ошибка в serial_exchange: {error}. Перезапуск через 5 минут..."
            )
            time.sleep(300)


if __name__ == '__main__':
    main()
