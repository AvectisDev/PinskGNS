import logging
from datetime import timedelta

from django.utils import timezone
from rest_framework import viewsets, status, serializers
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from drf_spectacular.utils import (
    extend_schema,
    extend_schema_view,
    inline_serializer,
    OpenApiExample
)
from ttn import services
from ttn.models import MiriadaTtn
from ttn.api.serializers import MiriadaTtnSerializer
from core.api.schema import ApiErrorSerializer


logger = logging.getLogger('filling_station')


@extend_schema_view(
    get_current_ttn=extend_schema(
        tags=['ТТН из Мириады'],
        summary='Получить список текущих ТТН',
        description='Получение списка текущих ТТН из системы Мириада',
        responses={
            200: MiriadaTtnSerializer(many=True),
            500: ApiErrorSerializer,
        },
        examples=[
            OpenApiExample(
                'Пример успешного ответа',
                value=[
                    {
                        "ttn_id": 14769,
                        "name": "ТТН №0324344",
                        "auto": "AM 9621-1",
                        "date": "2025-12-18"
                    },
                    {
                        "ttn_id": 14796,
                        "name": "0324576",
                        "auto": "АН 5514-1",
                        "date": "2025-12-18"
                    },
                ],
                response_only=True
            ),
            OpenApiExample(
                'Пример ошибки',
                value={
                    'error': 'Не удалось получить список ТТН из Мириады'
                },
                response_only=True,
                status_codes=['500']
            )
        ]
    )
)
class MiriadaTtnViewSet(viewsets.ViewSet):
    """
    API для работы с ТТН из системы Мириада.
    AllowAny: мобильное приложение запрашивает список до/без JWT.
    Пустая authentication_classes: просроченный Bearer не должен давать 401.
    """
    authentication_classes = []
    permission_classes = [AllowAny]

    @action(detail=False, methods=['get'], url_path='current', url_name='current')
    def get_current_ttn(self, request):
        """
        Получение списка текущих ТТН из системы Мириада, сохранение в БД и возврат.

        Returns:
            Response: Список ТТН с полями id, name, auto, date
        """
        try:
            services.sync_current_ttn_from_miriada()
        except Exception as e:
            logger.error(f"Ошибка при синхронизации ТТН из Мириады: {e}")

        start_date = timezone.localdate() - timedelta(days=5)
        local_ttn = MiriadaTtn.objects.filter(date__gte=start_date)
        serializer = MiriadaTtnSerializer(local_ttn, many=True)
        return Response(serializer.data)
