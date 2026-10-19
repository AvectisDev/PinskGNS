"""Сервис жизненного цикла партий баллонов: пауза, закрытие, отправка в Мириаду."""

import logging
from concurrent.futures import CancelledError, ThreadPoolExecutor, as_completed
from typing import Any, Dict, Optional, Tuple

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from filling_station.exceptions import MiriadaAPIError
from filling_station.models import Balloon, BalloonsBatch, BatchStatus
from filling_station.services.miriada import (
    get_thread_miriada_session,
    post_status_to_miriada,
    prepare_payload_for_miriada,
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
    """
    Возвращает queryset партий того же типа и считывателя за сегодня.

    Args:
        batch (BalloonsBatch): эталонная партия (тип, считыватель).

    Returns:
        QuerySet: партии BalloonsBatch за текущую локальную дату.
    """
    return BalloonsBatch.objects.filter(
        batch_type=batch.batch_type,
        reader_number=batch.reader_number,
        started_at__date=timezone.localdate(),
    )


def pause_other_active_batches_on_reader(batch: BalloonsBatch) -> int:
    """
    Ставит на паузу другие активные партии на том же считывателе за сегодня.

    Args:
        batch (BalloonsBatch): партия, которую оставляют активной.

    Returns:
        int: число обновлённых записей.
    """
    return (
        _today_batch_queryset(batch)
        .filter(status=BatchStatus.ACTIVE)
        .exclude(pk=batch.pk)
        .update(status=BatchStatus.PAUSED)
    )


@transaction.atomic
def pause_balloons_batch(batch: BalloonsBatch) -> Tuple[bool, str]:
    """
    Переводит партию из ACTIVE в PAUSED.

    Args:
        batch (BalloonsBatch): партия для приостановки.

    Returns:
        tuple[bool, str]: успех и текст ошибки (пустая строка при успехе).
    """
    if batch.status != BatchStatus.ACTIVE:
        return False, 'Партия не в работе'
    batch.status = BatchStatus.PAUSED
    batch.save(update_fields=['status'])
    logger.info(f"Партия {batch.id} приостановлена")
    return True, ''


@transaction.atomic
def resume_balloons_batch(batch: BalloonsBatch) -> Tuple[bool, str]:
    """
    Возобновляет приостановленную партию и ставит на паузу другие активные на ридере.

    Args:
        batch (BalloonsBatch): партия для возобновления.

    Returns:
        tuple[bool, str]: успех и текст ошибки (пустая строка при успехе).
    """
    if batch.status != BatchStatus.PAUSED:
        return False, 'Партия не приостановлена'
    pause_other_active_batches_on_reader(batch)
    batch.status = BatchStatus.ACTIVE
    batch.save(update_fields=['status'])
    logger.info(f"Партия {batch.id} возобновлена")
    return True, ''


def should_defer_balloon_status_to_batch_close(reader_number: int) -> bool:
    """
    Для рамки 3/4/6 статус уходит при добавлении в партию, а не из FEIG-протокола.
    Наполнение (ридер 8) по-прежнему шлётся сразу из FEIG.

    Args:
        reader_number (int): номер RFID-считывателя.

    Returns:
        bool: True, если FEIG не должен слать статус сам (отправка через партию).
    """
    if reader_number not in MIRIADA_BATCH_STATUS_READERS:
        return False
    return BalloonsBatch.objects.filter(
        reader_number=reader_number,
        started_at__date=timezone.localdate(),
        status=BatchStatus.ACTIVE,
    ).exists()


def should_send_balloon_status_immediately(reader_number: int) -> bool:
    """
    Из FEIG на лету в Мириаду уходит только наполнение (ридер 8).
    Рамка 3/4/6 отправляет статус при добавлении баллона в партию.

    Args:
        reader_number (int): номер RFID-считывателя.

    Returns:
        bool: True, если статус нужно отправить сразу после сканирования в FEIG.
    """
    return reader_number in MIRIADA_FILLING_READERS


def _set_balloon_status_error(batch: BalloonsBatch, nfc_tag: str, error_message: str) -> None:
    """
    Записывает ошибку отправки статуса на баллон и в ``miriada_status_errors`` партии.

    Args:
        batch: партия, в которой лежит баллон.
        nfc_tag: NFC-метка баллона.
        error_message: текст ошибки Мириады.
    """
    Balloon.objects.filter(nfc_tag=nfc_tag).update(miriada_status_error=error_message)
    errors = dict(batch.miriada_status_errors or {})
    errors[nfc_tag] = error_message
    batch.miriada_status_errors = errors
    batch.miriada_balloons_sent = False
    batch.save(update_fields=['miriada_status_errors', 'miriada_balloons_sent'])


def _clear_balloon_status_error(batch: BalloonsBatch, nfc_tag: str) -> None:
    """
    Очищает ошибку отправки статуса у баллона и в ``miriada_status_errors`` партии.

    Args:
        batch: партия, в которой лежит баллон.
        nfc_tag: NFC-метка баллона.
    """
    Balloon.objects.filter(nfc_tag=nfc_tag).update(miriada_status_error='')
    errors = dict(batch.miriada_status_errors or {})
    if nfc_tag in errors:
        errors.pop(nfc_tag, None)
        batch.miriada_status_errors = errors
        batch.save(update_fields=['miriada_status_errors'])


def add_balloon_to_batch_by_nfc(batch: BalloonsBatch, nfc_tag: str) -> dict:
    """
    Добавляет баллон в партию и сразу отправляет его статус в Мириаду.

    Добавление в партию считается успешным даже если Мириада отклонила баллон:
    текст ошибки пишется на баллон и в ``miriada_status_errors`` партии.

    Args:
        batch (BalloonsBatch): целевая партия.
        nfc_tag (str): NFC-метка баллона.

    Returns:
        dict: результат ``batch.add_balloon`` (success, message и связанные поля).
    """
    result = batch.add_balloon(nfc_tag)
    if not result.get('success'):
        return result

    reader_number = batch.reader_number
    if reader_number not in MIRIADA_BATCH_STATUS_READERS:
        return result

    batch.refresh_from_db()
    try:
        prepared_batch = BalloonsBatch.objects.select_related(
            'truck', 'truck__type', 'trailer'
        ).get(pk=batch.pk)
        url, payload, send_type = prepare_payload_for_miriada(
            reader_number, nfc_tag, batch=prepared_batch
        )
        post_status_to_miriada(url, payload, send_type)
        _clear_balloon_status_error(batch, nfc_tag)
        logger.info(
            f"Статус баллона {nfc_tag} отправлен в Мириаду при добавлении в партию {batch.id}"
        )
    except (MiriadaAPIError, ValueError) as exc:
        error_text = str(exc)
        _set_balloon_status_error(batch, nfc_tag, error_text)
        logger.error(
            f"Ошибка отправки статуса баллона {nfc_tag} в Мириаду "
            f"при добавлении в партию {batch.id}: {exc}"
        )

    return result


def _truncate_batch_error_message(error_message: Optional[str]) -> Optional[str]:
    """
    Обрезает текст ошибки Мириады до max_length поля модели.

    Args:
        error_message (str | None): исходное сообщение об ошибке.

    Returns:
        str | None: обрезанное сообщение или исходное значение.
    """
    if not error_message:
        return error_message
    max_len = BalloonsBatch._meta.get_field('miriada_error_message').max_length
    if max_len and len(error_message) > max_len:
        return error_message[: max_len - 3] + '...'
    return error_message


def _count_mismatch_payload(batch: BalloonsBatch) -> dict:
    """
    Формирует payload ответа при расхождении RFID и электронной ТТН.

    Args:
        batch (BalloonsBatch): партия со счётчиками.

    Returns:
        dict: сообщение и числовые поля для API-ответа.
    """
    message = (
        f'Количество отсканированных RFID ({batch.rfid_balloon_count()}) '
        f'не совпадает с количеством по электронной ТТН ({batch.amount_of_ttn or 0})'
    )
    return {
        'message': message,
        'count_mismatch': True,
        'amount_of_ttn': batch.amount_of_ttn or 0,
        'amount_of_rfid': batch.rfid_balloon_count(),
        'amount_of_sensor': batch.amount_of_sensor or 0,
        'id': batch.id,
    }


def _mark_batch_close_failed(batch: BalloonsBatch, error_message: Optional[str]) -> None:
    """
    Помечает партию статусом MIRIADA_ERROR после неудачного закрытия.

    Args:
        batch (BalloonsBatch): закрываемая партия.
        error_message (str | None): текст ошибки для сохранения.
    """
    batch.status = BatchStatus.MIRIADA_ERROR
    batch.completed_at = timezone.now()
    batch.miriada_error_message = _truncate_batch_error_message(error_message)
    batch.save(update_fields=[
        'status',
        'completed_at',
        'miriada_close_failed',
        'miriada_error_message',
    ])


def _sync_balloon_status_errors(nfc_tags: list, status_errors: Dict[str, str]) -> None:
    """
    Пишет ошибки отправки на баллоны и очищает поле у успешно принятых меток.

    Args:
        nfc_tags: NFC меток, которые уходили в Мириаду.
        status_errors: словарь NFC → текст ошибки.
    """
    if not nfc_tags:
        return
    balloons = list(Balloon.objects.filter(nfc_tag__in=nfc_tags))
    for balloon in balloons:
        new_error = status_errors.get(balloon.nfc_tag, '')
        if balloon.miriada_status_error != new_error:
            balloon.miriada_status_error = new_error
            balloon.save(update_fields=['miriada_status_error'])


def send_batch_balloon_statuses_to_miriada(
    batch: BalloonsBatch,
    nfc_tags: Optional[list] = None,
) -> Tuple[bool, Optional[str]]:
    """
    Отправляет в Мириаду статусы баллонов партии.

    HTTP идёт параллельно (лимит потоков MIRIADA_BATCH_SEND_WORKERS).
    Отказы Result=Error собираются по меткам и пишутся на баллоны
    и в ``miriada_status_errors`` партии. ``closettn`` здесь не вызывается.

    Args:
        batch (BalloonsBatch): партия, статусы баллонов которой отправляются.
        nfc_tags: ограниченный список меток; ``None`` — все баллоны партии.

    Returns:
        tuple[bool, str | None]: успех и текст ошибки (или None).
    """
    reader_number = batch.reader_number
    if reader_number not in MIRIADA_BATCH_STATUS_READERS:
        batch.miriada_balloons_sent = True
        batch.miriada_status_errors = {}
        batch.save(update_fields=['miriada_balloons_sent', 'miriada_status_errors'])
        return True, None

    prepared_batch = BalloonsBatch.objects.select_related(
        'truck', 'truck__type', 'trailer'
    ).get(pk=batch.pk)
    if nfc_tags is None:
        tags_to_send = list(prepared_batch.balloon_list.values_list('nfc_tag', flat=True))
    else:
        tags_to_send = list(nfc_tags)
    if not tags_to_send:
        if not _batch_has_balloon_status_errors(batch):
            batch.miriada_balloons_sent = True
            batch.miriada_status_errors = {}
            batch.save(update_fields=['miriada_balloons_sent', 'miriada_status_errors'])
        return True, None

    jobs = []
    for nfc_tag in tags_to_send:
        try:
            url, payload, send_type = prepare_payload_for_miriada(
                reader_number, nfc_tag, batch=prepared_batch
            )
        except ValueError as exc:
            error_msg = f"Ошибка подготовки данных для отправки: {exc}"
            logger.error(error_msg)
            batch.miriada_balloons_sent = False
            batch.save(update_fields=['miriada_balloons_sent'])
            return False, error_msg
        jobs.append((nfc_tag, url, payload, send_type))

    def _send_job(job: Tuple[str, str, Dict[str, Any], str]) -> str:
        """
        Отправляет один подготовленный статус баллона в Мириаду.

        Args:
            job: кортеж (nfc_tag, url, payload, send_type).

        Returns:
            str: NFC-метка успешно отправленного баллона.
        """
        nfc_tag, url, payload, send_type = job
        post_status_to_miriada(
            url,
            payload,
            send_type,
            session=get_thread_miriada_session(),
        )
        return nfc_tag

    max_workers = max(1, min(settings.MIRIADA_BATCH_SEND_WORKERS, len(jobs)))
    status_errors: Dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_tag = {
            executor.submit(_send_job, job): job[0] for job in jobs
        }
        for future in as_completed(future_to_tag):
            nfc_tag = future_to_tag[future]
            try:
                future.result()
            except MiriadaAPIError as exc:
                status_errors[nfc_tag] = str(exc)
                logger.error(
                    f'Ошибка отправки статуса баллона {nfc_tag} в Мириаду: {exc}'
                )
            except CancelledError:
                continue

    previous_errors = dict(batch.miriada_status_errors or {})
    for nfc_tag in tags_to_send:
        if nfc_tag not in status_errors:
            previous_errors.pop(nfc_tag, None)
    previous_errors.update(status_errors)
    batch.miriada_status_errors = previous_errors
    _sync_balloon_status_errors(tags_to_send, status_errors)

    if status_errors:
        batch.miriada_balloons_sent = False
        batch.save(update_fields=['miriada_balloons_sent', 'miriada_status_errors'])
        error_msg = f'Мириада отклонила {len(status_errors)} баллонов'
        logger.error(f'Партия {batch.id}: {error_msg}')
        return False, error_msg

    batch.miriada_balloons_sent = not bool(previous_errors)
    batch.save(update_fields=['miriada_balloons_sent', 'miriada_status_errors'])
    logger.info(
        f"В Мириаду отправлены статусы {len(tags_to_send)} баллонов партии {batch.id}"
    )
    return True, None


def _batch_has_balloon_status_errors(batch: BalloonsBatch) -> bool:
    """Есть ли у баллонов партии непустой miriada_status_error."""
    return batch.balloon_list.exclude(miriada_status_error='').exists()


def _error_balloon_nfc_tags(batch: BalloonsBatch) -> list:
    """NFC-метки баллонов партии с непустой ошибкой отправки в Мириаду."""
    return list(
        batch.balloon_list.exclude(miriada_status_error='').values_list('nfc_tag', flat=True)
    )


def attempt_close_balloons_batch(batch: BalloonsBatch) -> Tuple[bool, Optional[str]]:
    """
    Закрывает партию через ``closettn``.

    Перед вызовом ожидаются: совпадение RFID с ТТН и отсутствие ошибок на баллонах.
    Повторная отправка статусов выполняется в ``save_and_close_balloons_batch``.

    Args:
        batch (BalloonsBatch): партия для закрытия.

    Returns:
        tuple[bool, str | None]: успех и текст ошибки (или None при успехе).
    """
    from ttn.services import close_ttn_in_miriada

    if batch.amount_of_ttn:
        if batch.rfid_balloon_count() != batch.amount_of_ttn:
            return False, _count_mismatch_payload(batch)['message']

    if _batch_has_balloon_status_errors(batch):
        return False, 'В партии есть баллоны с ошибкой отправки в Мириаду'

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
        batch.miriada_status_errors = {}
        batch.miriada_balloons_sent = True
    else:
        batch.status = BatchStatus.MIRIADA_ERROR
        batch.miriada_error_message = _truncate_batch_error_message(error_message)
    batch.save(update_fields=[
        'status',
        'completed_at',
        'miriada_close_failed',
        'miriada_error_message',
        'miriada_status_errors',
        'miriada_balloons_sent',
    ])

    if success:
        return True, None
    return False, error_message


BATCH_CLOSE_WRITABLE_FIELDS = frozenset({
    'truck',
    'trailer',
    'reader_number',
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


def save_and_close_balloons_batch(batch: BalloonsBatch):
    """
    Повторяет ошибочные статусы баллонов и закрывает ТТН.

    Порядок: повтор только баллонов с ошибкой → сверка RFID с ТТН →
    отсутствие ошибок на баллонах → ``closettn``.
    Применение writable-полей партии — ответственность caller (API/views).

    Args:
        batch (BalloonsBatch): партия для закрытия.

    Returns:
        tuple: (успех, ошибка/payload или None).
    """
    error_tags = _error_balloon_nfc_tags(batch)
    if error_tags:
        send_batch_balloon_statuses_to_miriada(batch, nfc_tags=error_tags)
        batch.refresh_from_db()
        if _batch_has_balloon_status_errors(batch):
            return False, {
                'message': 'В партии есть баллоны с ошибкой отправки в Мириаду',
                'balloon_status_errors': True,
                'id': batch.id,
                'status': batch.status,
            }

    if batch.amount_of_ttn and batch.rfid_balloon_count() != batch.amount_of_ttn:
        return False, _count_mismatch_payload(batch)

    if _batch_has_balloon_status_errors(batch):
        return False, {
            'message': 'В партии есть баллоны с ошибкой отправки в Мириаду',
            'balloon_status_errors': True,
            'id': batch.id,
            'status': batch.status,
        }

    success, error_message = attempt_close_balloons_batch(batch)
    batch.refresh_from_db()

    if success:
        return True, None

    return False, {
        'message': error_message,
        'miriada_close_failed': True,
        'miriada_error_message': batch.miriada_error_message,
        'id': batch.id,
        'status': batch.status,
    }
