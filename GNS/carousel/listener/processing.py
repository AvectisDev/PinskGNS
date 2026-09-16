"""
Бизнес-обработка запросов постов наполнения.

Связывает бинарный протокол с Redis (очередь паспортов RFID),
настройками карусели (ORM) и сервисом сохранения данных.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from django.core.exceptions import ValidationError

from carousel.services import (
    CarouselPostNotFoundError,
    UnsupportedCarouselRequestError,
    get_carousel_settings_data,
    process_carousel_data_direct,
)
from carousel.validation import is_value_in_range
from core.redis_queue import increment_metric, pop_json_from_queue

from .protocol import (
    REQUEST_TYPE_FILL_STR,
    REQUEST_TYPE_FULL_WEIGHT_STR,
)

logger = logging.getLogger('carousel')


@dataclass(frozen=True)
class PostSettings:
    """Настройки обработки одного поста карусели."""

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
    carousel_number: int,
    post_number: int | None,
    request_type: str | None,
    error_code: str,
    message: str,
    metric_name: str = 'post_errors',
) -> None:
    """Логирует ошибку поста и увеличивает счётчик метрики в Redis."""
    logger.error(
        "Карусель=%s пост=%s тип=%s ошибка=%s: %s",
        carousel_number,
        post_number,
        request_type,
        error_code,
        message,
    )
    try:
        increment_metric(carousel_number, metric_name)
    except Exception as error:
        logger.error(f"Не удалось обновить метрику {metric_name}: {error}")


def get_and_remove_last_balloon(
    carousel_number: int,
    balloon_queue_key: str,
    post_number: int,
    request_type: str,
) -> tuple[dict | None, bool]:
    """
    Атомарно извлекает самый старый паспорт из нативной Redis-очереди.

    Returns:
        (balloon_dict, queue_available) — queue_available=False при ошибке Redis.
    """
    try:
        balloon, queue_size = pop_json_from_queue(balloon_queue_key)
        logger.debug(
            f"Карусель={carousel_number} очередь={balloon_queue_key} "
            f"размер={queue_size}"
        )
        return balloon, True
    except Exception as error:
        record_post_error(
            carousel_number,
            post_number,
            request_type,
            'queue_read_error',
            str(error),
            metric_name='queue_errors',
        )
        return None, False


def put_carousel_data(carousel_number: int, data: dict) -> bool:
    """
    Сохраняет показания поста карусели через сервис Django.

    Args:
        carousel_number: Номер карусели (для метрик/логов).
        data: Словарь с request_type, post_number, весами и паспортом баллона.

    Returns:
        True при успешном сохранении.
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
            carousel_number,
            data.get('post_number'),
            data.get('request_type'),
            'persistence_validation_error',
            str(error),
        )
    except Exception as error:
        record_post_error(
            carousel_number,
            data.get('post_number'),
            data.get('request_type'),
            'persistence_error',
            str(error),
        )
        logger.exception("Ошибка сохранения данных с поста наполнения")
    return False


def check_settings(carousel_number: int, post_number: int) -> PostSettings:
    """Читает настройки обработки постов из in-memory кэша (sync Redis при смене rev)."""
    from carousel.settings_cache import sync_from_redis_if_stale

    sync_from_redis_if_stale()
    post_settings = get_carousel_settings_data(carousel_number)
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


def check_balloon_size(
    weight: int,
    *,
    classify: bool = False,
    size_27_max_g: int = 16000,
) -> int:
    """
    Определяет объём баллона по весу пустого баллона на посту (граммы).

    Если classify выключен — всегда 50 л.
    Если включён: weight <= size_27_max_g → 27, иначе 50.
    При weight <= 0 — fallback 50 с WARNING.
    """
    if not classify:
        return 50
    if weight <= 0:
        logger.warning(
            'Некорректный вес пустого баллона %s г — объём по умолчанию 50 л',
            weight,
        )
        return 50
    if weight <= size_27_max_g:
        return 27
    return 50


def request_processing(
    carousel_number: int,
    balloon_queue_key: str,
    request_type: str,
    post_number: int,
    weight: int,
) -> tuple[bool, int, dict]:
    """
    Обрабатывает запрос от поста наполнения.

    0x7a — пустой баллон: извлекает паспорт из Redis, валидирует веса,
    при успехе формирует целевой полный вес для ответа посту.
    0x70 — полный баллон: фиксирует итоговый вес для записи в БД.

    Returns:
        response_required — нужно ли отправлять ответ на пост
        full_weight — целевой полный вес в граммах (для 0x7A)
        process_data_to_server — данные для сохранения в Django
    """
    response_required = False
    full_weight = 0
    settings_data = get_carousel_settings_data(carousel_number) or {}
    balloon_size = check_balloon_size(
        weight,
        classify=bool(settings_data.get('classify_size_by_weight')),
        size_27_max_g=int(
            settings_data.get('size_27_empty_weight_max_g') or 16000
        ),
    )
    process_data_to_server = {
        'carousel_number': carousel_number,
        'request_type': request_type,
        'post_number': post_number,
        'size': balloon_size,
    }

    if request_type == REQUEST_TYPE_FILL_STR:
        logger.debug("Запрос 0x7a")

        balloon_from_cache, queue_available = get_and_remove_last_balloon(
            carousel_number,
            balloon_queue_key,
            post_number,
            request_type,
        )

        if balloon_from_cache is None:
            if queue_available:
                record_post_error(
                    carousel_number,
                    post_number,
                    request_type,
                    'empty_balloon_queue',
                    f'В очереди {balloon_queue_key} нет паспорта баллона',
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
                carousel_number,
                post_number,
                request_type,
                'balloon_not_ready',
                'Паспорт баллона не разрешает наполнение',
                metric_name='passport_errors',
            )
        elif netto is None or brutto is None:
            record_post_error(
                carousel_number,
                post_number,
                request_type,
                'incomplete_passport',
                f'Неполный паспорт: netto={netto}, brutto={brutto}',
                metric_name='passport_errors',
            )
        else:
            post_settings = check_settings(carousel_number, post_number)
            if not post_settings.available:
                record_post_error(
                    carousel_number,
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
                        carousel_number,
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
                        carousel_number,
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
                        carousel_number,
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
                        carousel_number,
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
                        carousel_number,
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

    elif request_type == REQUEST_TYPE_FULL_WEIGHT_STR:
        process_data_to_server['full_weight'] = weight / 1000
    else:
        record_post_error(
            carousel_number,
            post_number,
            request_type,
            'unknown_request_type',
            f'Неизвестный тип запроса {request_type}',
        )

    return response_required, full_weight, process_data_to_server
