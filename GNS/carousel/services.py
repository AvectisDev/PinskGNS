from __future__ import annotations

from typing import Any, Mapping, Optional

from django.core.exceptions import ValidationError
from django.db import close_old_connections, transaction

from .models import Carousel, CarouselSettings


class CarouselPostNotFoundError(Exception):
    """Запрошенный пост карусели отсутствует в базе данных."""


class UnsupportedCarouselRequestError(Exception):
    """Карусель передала неизвестный тип запроса."""


CAROUSEL_CREATE_FIELDS = frozenset({
    'carousel_number',
    'is_empty',
    'post_number',
    'empty_weight',
    'full_weight',
    'nfc_tag',
    'serial_number',
    'size',
    'netto',
    'brutto',
    'filling_status',
})


def get_carousel_settings_data() -> Optional[dict[str, Any]]:
    """Возвращает настройки карусели через Django ORM."""
    close_old_connections()
    try:
        return CarouselSettings.objects.order_by('pk').values().first()
    finally:
        close_old_connections()


@transaction.atomic
def process_carousel_data(data: Mapping[str, Any]) -> Carousel:
    """
    Сохраняет данные от карусели без промежуточного HTTP-запроса.

    Ветки по request_type:
        0x7a — создаёт новую запись Carousel (пустой баллон, паспорт RFID).
        0x70 — обновляет последнюю запись поста: is_empty=False, full_weight.

    Raises:
        ValidationError: Не указан request_type.
        CarouselPostNotFoundError: Для 0x70 нет записи поста.
        UnsupportedCarouselRequestError: Неизвестный тип запроса.
    """
    request_type = data.get('request_type')

    if request_type == '0x7a':
        create_data = {
            key: value
            for key, value in data.items()
            if key in CAROUSEL_CREATE_FIELDS
        }
        carousel_post = Carousel(**create_data)
        carousel_post.full_clean()
        carousel_post.save()
        return carousel_post

    if request_type == '0x70':
        post_number = data.get('post_number')
        carousel_post = (
            Carousel.objects.select_for_update()
            .filter(post_number=post_number)
            .order_by('-change_at', '-pk')
            .first()
        )
        if carousel_post is None:
            raise CarouselPostNotFoundError(f'Пост {post_number} не найден')

        carousel_post.is_empty = False
        update_fields = ['is_empty', 'change_at']
        if 'full_weight' in data:
            carousel_post.full_weight = data['full_weight']
            update_fields.append('full_weight')
        carousel_post.full_clean()
        carousel_post.save(update_fields=update_fields)
        return carousel_post

    if not request_type:
        raise ValidationError({'request_type': 'Не указан тип запроса'})

    raise UnsupportedCarouselRequestError(
        f'Неизвестный тип запроса: {request_type}'
    )


def process_carousel_data_direct(data: Mapping[str, Any]) -> Carousel:
    """Обёртка для вызова ORM из долгоживущего listener-процесса карусели."""
    close_old_connections()
    try:
        return process_carousel_data(data)
    finally:
        close_old_connections()
