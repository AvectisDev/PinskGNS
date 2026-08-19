import logging
from concurrent.futures import CancelledError, ThreadPoolExecutor, as_completed
from typing import Any, Dict, Optional, Tuple

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from filling_station.exceptions import MiriadaAPIError
from filling_station.models import BalloonsBatch, BatchStatus
from filling_station.services.miriada import (
    _prepare_payload_for_miriada,
    get_thread_miriada_session,
    post_status_to_miriada,
)

logger = logging.getLogger('filling_station')

MIRIADA_BATCH_STATUS_READERS = frozenset({3, 4, 6})
MIRIADA_FILLING_READERS = frozenset({8})
MIRIADA_BALLOON_STATUS_READERS = MIRIADA_BATCH_STATUS_READERS | MIRIADA_FILLING_READERS

OPEN_BATCH_STATUSES = frozenset({
    BatchStatus.ACTIVE,
    BatchStatus.PAUSED,
    BatchStatus.MIRIADA_ERROR,
})


def _today_batch_queryset(batch: BalloonsBatch):
    return BalloonsBatch.objects.filter(
        batch_type=batch.batch_type,
        reader_number=batch.reader_number,
        started_at__date=timezone.localdate(),
    )


def pause_other_active_batches_on_reader(batch: BalloonsBatch) -> int:
    """Ставит на паузу другие активные партии на том же считывателе за сегодня."""
    return (
        _today_batch_queryset(batch)
        .filter(status=BatchStatus.ACTIVE)
        .exclude(pk=batch.pk)
        .update(status=BatchStatus.PAUSED)
    )


@transaction.atomic
def pause_balloons_batch(batch: BalloonsBatch) -> Tuple[bool, str]:
    if batch.status != BatchStatus.ACTIVE:
        return False, 'Партия не в работе'
    batch.status = BatchStatus.PAUSED
    batch.save(update_fields=['status'])
    logger.info(f"Партия {batch.id} приостановлена")
    return True, ''


@transaction.atomic
def resume_balloons_batch(batch: BalloonsBatch) -> Tuple[bool, str]:
    if batch.status != BatchStatus.PAUSED:
        return False, 'Партия не приостановлена'
    pause_other_active_batches_on_reader(batch)
    batch.status = BatchStatus.ACTIVE
    batch.save(update_fields=['status'])
    logger.info(f"Партия {batch.id} возобновлена")
    return True, ''


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
        status=BatchStatus.ACTIVE,
    ).exists()


def should_send_balloon_status_immediately(reader_number: int) -> bool:
    """На лету в Мириаду уходит только наполнение (ридер 8). Рамка 3/4/6 — при закрытии."""
    return reader_number in MIRIADA_FILLING_READERS


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


def _mark_batch_close_failed(batch: BalloonsBatch, error_message: Optional[str]) -> None:
    batch.status = BatchStatus.MIRIADA_ERROR
    batch.completed_at = timezone.now()
    batch.miriada_error_message = _truncate_batch_error_message(error_message)
    batch.save(update_fields=[
        'status',
        'completed_at',
        'miriada_close_failed',
        'miriada_error_message',
    ])


def send_batch_balloon_statuses_to_miriada(batch: BalloonsBatch) -> Tuple[bool, Optional[str]]:
    """
    Отправляет в Мириаду статусы всех баллонов партии тем же методом,
    что раньше вызывался в момент сканирования на рамке.

    HTTP идёт параллельно (лимит потоков MIRIADA_BATCH_SEND_WORKERS),
    у каждого потока своя keep-alive сессия. Payload готовится заранее,
    чтобы не ходить в ORM из воркеров.
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
    if not nfc_tags:
        batch.miriada_balloons_sent = True
        batch.save(update_fields=['miriada_balloons_sent'])
        return True, None

    jobs = []
    for nfc_tag in nfc_tags:
        try:
            url, payload, send_type = _prepare_payload_for_miriada(
                reader_number, nfc_tag, batch=prepared_batch
            )
        except ValueError as exc:
            error_msg = f"Ошибка подготовки данных для отправки: {exc}"
            logger.error(error_msg)
            return False, error_msg
        jobs.append((nfc_tag, url, payload, send_type))

    def _send_job(job: Tuple[str, str, Dict[str, Any], str]) -> str:
        nfc_tag, url, payload, send_type = job
        post_status_to_miriada(
            url,
            payload,
            send_type,
            session=get_thread_miriada_session(),
        )
        return nfc_tag

    max_workers = max(1, min(settings.MIRIADA_BATCH_SEND_WORKERS, len(jobs)))
    first_error: Optional[str] = None
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_tag = {
            executor.submit(_send_job, job): job[0] for job in jobs
        }
        for future in as_completed(future_to_tag):
            nfc_tag = future_to_tag[future]
            try:
                future.result()
            except MiriadaAPIError as exc:
                if first_error is None:
                    first_error = f'Ошибка отправки статуса баллона {nfc_tag} в Мириаду: {exc}'
                    logger.error(first_error)
                    for pending in future_to_tag:
                        if not pending.done():
                            pending.cancel()
            except CancelledError:
                continue

    if first_error:
        return False, first_error

    batch.miriada_balloons_sent = True
    batch.save(update_fields=['miriada_balloons_sent'])
    logger.info(
        f"В Мириаду отправлены статусы {len(nfc_tags)} баллонов партии {batch.id}"
    )
    return True, None


def attempt_close_balloons_batch(batch: BalloonsBatch) -> Tuple[bool, Optional[str]]:
    """
    Закрывает партию баллонов.

    Сначала отправляет статусы всех баллонов партии в Мириаду, затем закрывает ТТН.
    """
    from ttn.services import close_ttn_in_miriada

    if batch.amount_of_ttn:
        if (batch.amount_of_rfid or 0) != batch.amount_of_ttn:
            return False, _count_mismatch_payload(batch)['message']

    statuses_ok, statuses_error = send_batch_balloon_statuses_to_miriada(batch)
    if not statuses_ok:
        _mark_batch_close_failed(batch, statuses_error)
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

    batch.completed_at = timezone.now()
    if success:
        batch.status = BatchStatus.COMPLETED
        batch.miriada_error_message = None
    else:
        batch.status = BatchStatus.MIRIADA_ERROR
        batch.miriada_error_message = _truncate_batch_error_message(error_message)
    batch.save(update_fields=[
        'status',
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

    if batch.status in (BatchStatus.ACTIVE, BatchStatus.PAUSED):
        return False, _count_mismatch_payload(batch), None

    return False, {
        'message': error_message,
        'miriada_close_failed': True,
        'miriada_error_message': batch.miriada_error_message,
        'id': batch.id,
        'status': batch.status,
    }, None
