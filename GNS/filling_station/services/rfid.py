import logging
from typing import Optional, Dict, Any, Tuple

from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone

from core.redis_queue import get_reader_balloon_queue_key, push_json_to_queue
from filling_station.exceptions import ReaderNotFoundError, MiriadaAPIError
from filling_station.models import (
    Balloon,
    Reader,
    BalloonsBatch,
    ReaderSettings,
    DailyReaderCounter,
    TotalReadersCounter,
)
from filling_station.services.miriada import get_balloon_data_from_miriada

logger = logging.getLogger('filling_station')


def processing_request_without_nfc(reader_number: int) -> Optional[ReaderSettings]:
    """
    Обрабатывает сигнал от ридера о сработке оптического датчика.

    Returns:
        ReaderSettings при успехе.

    Raises:
        ReaderNotFoundError: Если считыватель не найден
    """
    try:
        reader = ReaderSettings.objects.get(number=reader_number)

        DailyReaderCounter.add_sensor(reader)
        match reader.number:
            case 6:
                TotalReadersCounter.add_empty_balloon()
            case 5:
                TotalReadersCounter.add_full_balloon()
                TotalReadersCounter.sub_empty_balloon()
            case 3 | 4:
                TotalReadersCounter.sub_full_balloon()

        logger.info(f'Ридер {reader_number}. Создана запись баллона без NFC')

        if reader.function in ['l', 'u']:
            add_sensor_count_to_batch(reader)
        return reader
    except ObjectDoesNotExist:
        error_msg = f"Ридер {reader_number} не найден в настройках"
        logger.error(error_msg)
        raise ReaderNotFoundError(error_msg) from None
    except Exception as error:
        logger.error(f"Ошибка обработки сигнала от оптического датчика: {error}")
        raise


def processing_request_with_nfc(nfc_tag: str, reader_number: int) -> Optional[Tuple[Balloon, ReaderSettings]]:
    """Обрабатывает сигнал от ридера при получении метки."""
    try:
        reader = ReaderSettings.objects.get(number=reader_number)

        balloon, created = Balloon.objects.update_or_create(
            nfc_tag=nfc_tag,
            defaults={
                'status': reader.status
            }
        )
        logger.info(f"Ридер {reader.number}: Сохранение баллона с меткой {nfc_tag} успешно")

        DailyReaderCounter.add_rfid(reader)
        match reader.number:
            case 1:
                TotalReadersCounter.add_empty_balloon()
            case 2:
                TotalReadersCounter.sub_full_balloon()

        if balloon.update_passport_required or reader.number in [1, 6, 7, 8]:
            update_balloon_passport(balloon)

        if reader.function in ['l', 'u']:
            add_balloon_to_batch(reader, balloon)

        add_balloon_to_reader_table(balloon, reader)

        if reader.need_cache:
            add_balloon_to_cache(balloon, reader)

        return balloon, reader
    except ObjectDoesNotExist:
        error_msg = f"Ридер {reader_number} не найден в настройках"
        logger.error(error_msg)
        raise ReaderNotFoundError(error_msg) from None
    except Exception as error:
        logger.error(f"Ошибка при создании/изменении паспорта баллона: {error}")
        return None


def update_balloon_passport(balloon: Balloon) -> None:
    """Обрабатывает данные от API Мириады и обновляет запись баллона."""
    try:
        api_data = get_balloon_data_from_miriada(balloon.nfc_tag)
        if api_data:
            balloon.serial_number = api_data['number']
            balloon.netto = api_data['netto']
            balloon.brutto = api_data['brutto']
            balloon.filling_status = api_data['status']
            balloon.update_passport_required = False
            balloon.save()
            logger.info(f"Обновление паспорта баллона с меткой {balloon.nfc_tag} успешно")
    except MiriadaAPIError:
        raise
    except Exception as e:
        logger.error(f"Ошибка при обновлении паспорта баллона {balloon.nfc_tag}: {e}")
        raise


def get_active_batch_for_reader(reader: ReaderSettings) -> Optional[BalloonsBatch]:
    """Активная партия приёмки/отгрузки, привязанная к считывателю на сегодня."""
    if reader.function not in ['l', 'u']:
        return None
    return BalloonsBatch.objects.select_related('truck', 'trailer', 'truck__type').filter(
        batch_type=reader.function,
        started_at__date=timezone.localdate(),
        reader_number=reader.number,
        is_active=True,
    ).first()


def add_sensor_count_to_batch(reader: ReaderSettings) -> None:
    """Увеличивает счётчик оптического датчика у активной партии считывателя."""
    batch = get_active_batch_for_reader(reader)
    if not batch:
        return
    result = batch.add_balloon()
    if result.get('success'):
        logger.info(f"Оптический датчик: партия {batch.id}, считыватель {reader.number}")
    else:
        logger.warning(
            f"Не удалось учесть оптический датчик в партии {batch.id}: {result.get('message')}"
        )


def add_balloon_to_batch(reader: ReaderSettings, balloon: Optional[Balloon] = None) -> Optional[Dict[str, Any]]:
    """Добавляет баллон в активную партию в зависимости от номера ридера."""
    if not balloon:
        return None

    try:
        batch = get_active_batch_for_reader(reader)

        if not batch:
            logger.warning(f'Нет подходящей партии баллонов для ридера {reader.number}')
            return {'message': f'Нет подходящей партии баллонов'}

        result = batch.add_balloon(balloon.nfc_tag)
        if result.get('success', False):
            logger.info(f"Баллон {balloon.nfc_tag} добавлен в партию {batch.id}")
        else:
            logger.warning(f"Не удалось добавить баллон {balloon.nfc_tag} в партию: {result.get('message')}")

        return result
    except Exception as e:
        logger.error(f"Ошибка добавления баллона {balloon.nfc_tag if balloon else 'None'} в партию: {e}")
        return None


def add_balloon_to_reader_table(balloon: Balloon, reader: ReaderSettings) -> None:
    """Добавляет запись о прохождении баллона с меткой через определённый ридер."""
    try:
        Reader.objects.create(
            number=reader,
            nfc_tag=balloon.nfc_tag,
            serial_number=balloon.serial_number,
            size=balloon.size,
            netto=balloon.netto,
            brutto=balloon.brutto,
            filling_status=balloon.filling_status
        )
    except Exception as error:
        logger.error(f"Ошибка добавления баллона с NFC {balloon.nfc_tag} в таблицу считывателей: {error}")
        raise


def add_balloon_to_cache(balloon: Balloon, reader: ReaderSettings) -> None:
    """Добавляет паспорт баллона в нативную FIFO-очередь Redis."""
    cache_timeout_seconds = 10 * 60

    try:
        queue_key = get_reader_balloon_queue_key(reader.number)
        queue_length = push_json_to_queue(queue_key, {
            'nfc_tag': balloon.nfc_tag,
            'serial_number': balloon.serial_number,
            'size': balloon.size,
            'netto': balloon.netto,
            'brutto': balloon.brutto,
            'filling_status': balloon.filling_status,
        }, timeout=cache_timeout_seconds)
        logger.debug(
            f'Баллон с NFC {balloon.nfc_tag} добавлен в Redis-очередь '
            f'{queue_key}. Размер очереди: {queue_length}'
        )
    except Exception as error:
        logger.error(
            f"Ошибка добавления баллона с NFC {balloon.nfc_tag} "
            f"в Redis-очередь: {error}"
        )
        raise
