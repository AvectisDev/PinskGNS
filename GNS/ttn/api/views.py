import logging
from datetime import datetime, timezone
from rest_framework import viewsets, status, serializers
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny
from drf_spectacular.utils import (
    extend_schema,
    extend_schema_view,
    inline_serializer,
    OpenApiTypes,
    OpenApiExample
)
from ttn import services
from ttn.models import MiriadaTtn
from ttn.api.serializers import MiriadaTtnSerializer


logger = logging.getLogger('filling_station')


@extend_schema_view(
    get_current_ttn=extend_schema(
        tags=['ТТН из Мириады'],
        summary='Получить список текущих ТТН',
        description='Получение списка текущих ТТН из системы Мириада',
        responses={
            200: MiriadaTtnSerializer(many=True),
            404: OpenApiTypes.OBJECT,
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
    """
    permission_classes = [AllowAny]

    @action(detail=False, methods=['get'], url_path='current')
    def get_current_ttn(self, request):
        """
        Получение списка текущих ТТН из системы Мириада, сохранение в БД и возврат.

        Returns:
            Response: Список ТТН с полями id, name, auto, date
        """
        # Получаем данные из API Мириады
        api_response = services.get_current_ttn_from_miriada()

        # Сохраняем ТТН в базу данных
        saved_ttns = []
        try:
            for ttn_data in api_response:

                ttn_id = ttn_data.get('ttn_id')
                if not ttn_id:
                    logger.error(f"Отсутствует ID ТТН: {ttn_data}")
                    continue

                try:
                    miriada_ttn, created = MiriadaTtn.objects.update_or_create(
                        ttn_id=ttn_id,
                        defaults={
                            'name': ttn_data.get('name', ''),
                            'auto': ttn_data.get('auto', ''),
                            'date': ttn_data.get('date')
                        }
                    )
                    saved_ttns.append(miriada_ttn)

                    logger.info(
                        f"ТТН {'создана' if created else 'обновлена'}: ID={ttn_id}, name={ttn_data.get('name')}")

                except Exception as e:
                    logger.error(f"Ошибка сохранения ТТН ID={ttn_id}: {str(e)}")

        except Exception as e:
            logger.error(f"Транзакционная ошибка при сохранении ТТН: {e}")
            return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Сериализуем и возвращаем сохраненные данные
        if not saved_ttns:
            local_ttn = MiriadaTtn.objects.filter(date=datetime.today().date())
            
            if not local_ttn:
                return Response(status=status.HTTP_404_NOT_FOUND)
            
            serializer = MiriadaTtnSerializer(local_ttn, many=True)
            return Response(serializer.data)


        serializer = MiriadaTtnSerializer(saved_ttns, many=True)
        return Response(serializer.data)
