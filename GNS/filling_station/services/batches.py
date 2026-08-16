import logging
from typing import Optional, Tuple

from django.utils import timezone

from filling_station.exceptions import MiriadaAPIError
from filling_station.models import BalloonsBatch
from filling_station.services.miriada import send_status_to_miriada

logger = logging.getLogger('filling_station')

MIRIADA_BATCH_STATUS_READERS = frozenset({3, 4, 6})
MIRIADA_FILLING_READERS = frozenset({8})
MIRIADA_BALLOON_STATUS_READERS = MIRIADA_BATCH_STATUS_READERS | MIRIADA_FILLING_READERS


def should_defer_balloon_status_to_batch_close(reader_number: int) -> bool:
    """
    Статусы баллонов рамки приёмки/отгрузки (3/4/6) отправляются в Мириаду
    только при закрытии активной партии, а не в момент сканирования.
    Наполнение (ридер 8) по-прежнему уходит сразу.
    """
    if reader_number not in MIRIADA_BATCH_STATUS_READERS:
        return False
    return BalloonsBatch.objects.filter(
        reader_number=reader_number,
        started_at__date=timezone.localdate(),
        is_active=True,
    ).exists()


def should_send_balloon_status_immediately(reader_number: int) -> bool:
    if reader_number not in MIRIADA_BALLOON_STATUS_READERS:
        return False
    return not should_defer_balloon_status_to_batch_close(reader_number)


def add_balloon_to_batch_by_nfc(batch: BalloonsBatch, nfc_tag: str) -> dict:
    """
    Добавляет баллон в партию локально.
    Отправка статуса в Мириаду выполняется при закрытии партии.
    """
    return batch.add_balloon(nfc_tag)


def _truncate_batch_error_message(error_message: Optional[str]) -> Optional[str]:
    if not error_message:
        return error_message
    max_len = BalloonsBatch._meta.get_field('miriada_error_message').max_length
    if max_len and len(error_message) > max_len:
        return error_message[: max_len - 3] + '...'
    return error_message


def _count_mismatch_payload(batch: BalloonsBatch) -> dict:
    message = (
        f'Количество отсканированных RFID ({batch.amount_of_rfid or 0}) '
        f'не совпадает с количеством по электронной ТТН ({batch.amount_of_ttn or 0})'
    )
    return {
        'message': message,
        'count_mismatch': True,
        'amount_of_ttn': batch.amount_of_ttn or 0,
        'amount_of_rfid': batch.amount_of_rfid or 0,
        'amount_of_sensor': batch.amount_of_sensor or 0,
        'id': batch.id,
    }


def send_batch_balloon_statuses_to_miriada(batch: BalloonsBatch) -> Tuple[bool, Optional[str]]:
    """
    Отправляет в Мириаду статусы всех баллонов партии тем же методом,
    что раньше вызывался в момент сканирования на рамке.
    """
    if batch.miriada_balloons_sent:
        return True, None

    reader_number = batch.reader_number
    if reader_number not in MIRIADA_BATCH_STATUS_READERS:
        return True, None

    prepared_batch = BalloonsBatch.objects.select_related(
        'truck', 'truck__type', 'trailer'
    ).get(pk=batch.pk)
    nfc_tags = list(prepared_batch.balloon_list.values_list('nfc_tag', flat=True))

    for nfc_tag in nfc_tags:
        try:
            send_status_to_miriada(reader=reader_number, nfc_tag=nfc_tag, batch=prepared_batch)
        except MiriadaAPIError as exc:
            error_msg = f'Ошибка отправки статуса баллона {nfc_tag} в Мириаду: {exc}'
            logger.error(error_msg)
            return False, error_msg

    batch.miriada_balloons_sent = True
    batch.save(update_fields=['miriada_balloons_sent'])
    logger.info(
        f"В Мириаду отправлены статусы {len(nfc_tags)} баллонов партии {batch.id}"
    )
    return True, None


def attempt_close_balloons_batch(batch: BalloonsBatch) -> Tuple[bool, Optional[str]]:
    """
    Закрывает партию баллонов (устанавливает is_active=False, completed_at).

    Сначала отправляет статусы всех баллонов партии в Мириаду, затем закрывает ТТН.
    """
    from ttn.services import close_ttn_in_miriada

    if batch.amount_of_ttn:
        if (batch.amount_of_rfid or 0) != batch.amount_of_ttn:
            return False, _count_mismatch_payload(batch)['message']

    statuses_ok, statuses_error = send_batch_balloon_statuses_to_miriada(batch)
    if not statuses_ok:
        error_message = _truncate_batch_error_message(statuses_error)
        batch.miriada_close_failed = True
        batch.miriada_error_message = error_message
        batch.save(update_fields=['miriada_close_failed', 'miriada_error_message'])
        return False, statuses_error

    should_send = bool(batch.ttn_id)
    if should_send:
        if batch.truck and batch.truck.type and batch.truck.type.type == "Клетевоз":
            should_send = False

    success = True
    error_message: Optional[str] = None
    if should_send:
        close_success, close_error = close_ttn_in_miriada(batch.ttn_id, batch=batch)
        if not close_success:
            success = False
            error_message = close_error
            logger.warning(
                f"Не удалось закрыть ТТН {batch.ttn_id} в Мириаде при закрытии партии {batch.id}: "
                f"{close_error}"
            )

    batch.is_active = False
    batch.completed_at = timezone.now()
    batch.miriada_close_failed = not success
    batch.miriada_error_message = _truncate_batch_error_message(error_message) if not success else None
    batch.save(update_fields=[
        'is_active',
        'completed_at',
        'miriada_close_failed',
        'miriada_error_message',
    ])

    if success:
        return True, None
    return False, error_message


BATCH_CLOSE_WRITABLE_FIELDS = frozenset({
    'truck',
    'trailer',
    'reader_number',
    'amount_of_rfid',
    'amount_of_sensor',
    'amount_of_ttn',
    'amount_of_5_liters',
    'amount_of_12_liters',
    'amount_of_27_liters',
    'amount_of_50_liters',
    'gas_amount',
    'ttn_id',
    'balloons_type',
})


def save_and_close_balloons_batch(batch: BalloonsBatch, data=None):
    """
    Сохраняет данные партии, отправляет статусы баллонов в Мириаду и закрывает ТТН.
    Пустое тело запроса допустимо: берутся текущие данные партии из БД.
    """
    from filling_station.api.serializers import BalloonsBatchSerializer

    payload = {
        key: value
        for key, value in (data or {}).items()
        if key in BATCH_CLOSE_WRITABLE_FIELDS
    }

    if payload:
        serializer = BalloonsBatchSerializer(batch, data=payload, partial=True)
        if not serializer.is_valid():
            return False, serializer.errors, None
        serializer.save()
        batch.refresh_from_db()

    if batch.amount_of_ttn and (batch.amount_of_rfid or 0) != batch.amount_of_ttn:
        return False, _count_mismatch_payload(batch), None

    success, error_message = attempt_close_balloons_batch(batch)
    batch.refresh_from_db()

    if success:
        return True, None, BalloonsBatchSerializer(batch).data

    if batch.is_active and not batch.miriada_close_failed:
        return False, _count_mismatch_payload(batch), None

    return False, {
        'message': error_message,
        'miriada_close_failed': True,
        'miriada_error_message': batch.miriada_error_message,
        'id': batch.id,
    }, None
