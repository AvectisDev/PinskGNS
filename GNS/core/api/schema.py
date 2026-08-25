"""Общие схемы OpenAPI (только документация, не меняют ответы API)."""

from rest_framework import serializers


class ApiErrorSerializer(serializers.Serializer):
    """
    Единый формат ошибок в OpenAPI.

    Реальные ответы пока могут отличаться (`error` / `detail` / `errors`);
    схема фиксирует целевой контракт для клиентов и агентов.
    """

    error = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text='Человекочитаемое сообщение об ошибке',
    )
    detail = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text='Краткое описание (часто от DRF)',
    )
    code = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text='Машиночитаемый код ошибки (если задан)',
    )
    errors = serializers.DictField(
        child=serializers.JSONField(),
        required=False,
        help_text='Ошибки валидации по полям',
    )
