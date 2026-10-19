"""Общие схемы OpenAPI для ошибок (только документация, не меняют ответы API)."""

from drf_spectacular.utils import OpenApiExample, OpenApiResponse
from rest_framework import serializers


class MessageErrorSerializer(serializers.Serializer):
    """Бизнес-ошибка с одним полем ``message``."""

    message = serializers.CharField(help_text='Человекочитаемое сообщение об ошибке')


class DetailErrorSerializer(serializers.Serializer):
    """Ошибка DRF / get_object_or_404 с полем ``detail``."""

    detail = serializers.CharField(help_text='Краткое описание ошибки')


class ErrorFieldSerializer(serializers.Serializer):
    """Ошибка с одним полем ``error`` (строка или объект валидации)."""

    error = serializers.JSONField(
        help_text='Сообщение (строка) или ошибки валидации (объект)',
    )


# DRF validation: объект «имя поля → список строк».
FIELD_ERRORS_SCHEMA = {
    'type': 'object',
    'additionalProperties': {
        'type': 'array',
        'items': {'type': 'string'},
    },
    'example': {'status': ['Обязательное поле.']},
    'description': 'Ошибки валидации по полям (как у DRF serializer.errors)',
}

FIELD_ERRORS_RESPONSE = OpenApiResponse(
    response=FIELD_ERRORS_SCHEMA,
    description='Ошибки валидации полей',
    examples=[
        OpenApiExample(
            'Пример',
            value={'nfc_tag': ['Обязательное поле.'], 'size': ['Укажите целое число.']},
        ),
    ],
)

# Обратная совместимость импортов: раньше везде был ApiErrorSerializer.
# Оставляем алиас на message — самый частый бизнес-формат; callers должны
# постепенно указывать конкретный сериализатор.
ApiErrorSerializer = MessageErrorSerializer
