import logging
from rest_framework import viewsets, status, serializers
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import (
    extend_schema,
    extend_schema_view,
    inline_serializer,
    OpenApiTypes,
    OpenApiExample
)
from filling_station import services
from .serializers import TtnListResponseSerializer


logger = logging.getLogger('ttn')


@extend_schema_view(
    get_current_ttn=extend_schema(
        tags=['ТТН из Мириады'],
        summary='Получить список текущих ТТН',
        description='Получение списка текущих ТТН из системы Мириада',
        responses={
            200: TtnListResponseSerializer,
            500: inline_serializer(
                name='ErrorResponse',
                fields={
                    'error': serializers.CharField()
                }
            )
        },
        examples=[
            OpenApiExample(
                'Пример успешного ответа',
                value={
                    'ttn_list': [
                        {
                            'id': 12345,
                            'name': '123/1',
                            'auto': '2222 AH-2',
                            'date': '2024-01-15T10:30:00Z'
                        },
                        {
                            'id': 12346,
                            'name': '124/1',
                            'auto': '3333 BH-3',
                            'date': '2024-01-15T11:00:00Z'
                        }
                    ]
                },
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
    """
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'], url_path='current')
    def get_current_ttn(self, request):
        """
        Получение списка текущих ТТН из системы Мириада.
        
        Возвращает список активных ТТН с полями:
        - id: ID ТТН в системе Мириада
        - name: Номер ТТН
        - auto: Номер автомобиля
        - date: Дата ТТН
        
        Returns:
            Response: Список ТТН с полями id, name, auto, date
        """
        ttn_list = services.get_current_ttn_from_miriada()
        if ttn_list is None:
            logger.error("Не удалось получить список ТТН из Мириады")
            return Response(
                {"error": "Не удалось получить список ТТН из Мириады"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        return Response({"ttn_list": ttn_list})

