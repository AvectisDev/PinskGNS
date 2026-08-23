from django.shortcuts import get_object_or_404
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from rest_framework import status, viewsets
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import (
    extend_schema,
    extend_schema_view,
    OpenApiTypes,
    OpenApiExample
)
from autogas.models import AutoGasBatch
from autogas.services import (
    clear_statistic_cache,
    get_batch_statistic,
    get_today_active_batches,
    with_completed_at_on_deactivate,
)
from .serializers import AutoGasBatchSerializer
from core.api.schema import ApiErrorSerializer


@extend_schema_view(
    auto_batch_statistic=extend_schema(
        tags=['Автоцистерны'],
        summary='Получить статистику по автоцистернам',
        description='Получение сводной статистики по партиям автоцистерн. '
                    'Включает статистику за последний месяц и за сегодня, а также информацию об активной партии.',
        responses={
            200: OpenApiTypes.OBJECT
        },
        examples=[
            OpenApiExample(
                'Пример ответа',
                value={
                    'loading_batch': {
                        'ПБА': {
                            'gas_type': 'ПБА',
                            'batch_type': 'l',
                            'last_month_loading_batches': 15,
                            'last_month_loading_weight': 200000.50,
                            'today_loading_batches': 2,
                            'today_loading_weight': 30000.00
                        },
                        'СПБТ': {
                            'gas_type': 'СПБТ',
                            'batch_type': 'l',
                            'last_month_loading_batches': 10,
                            'last_month_loading_weight': 150000.25,
                            'today_loading_batches': 1,
                            'today_loading_weight': 15000.00
                        }
                    },
                    'unloading_batch': {
                        'ПБА': {
                            'gas_type': 'ПБА',
                            'batch_type': 'u',
                            'last_month_unloading_batches': 12,
                            'last_month_unloading_weight': 180000.00,
                            'today_unloading_batches': 1,
                            'today_unloading_weight': 15000.00
                        }
                    },
                    'active_batch': {
                        'batch_type': 'Приёмка',
                        'gas_type': 'ПБА',
                        'car_brand': 'МАЗ',
                        'truck_number': 'AM12347',
                        'trailer_number': 'AB12347',
                        'truck_gas_capacity': 20000.0,
                        'scale_empty_weight': 15000.0,
                        'scale_full_weight': 35000.0
                    }
                },
                response_only=True
            )
        ]
    ),
    list=extend_schema(
        tags=['Автоцистерны'],
        summary='Получить активные партии',
        description='Получение списка активных партий автоцистерн за сегодня',
        responses={
            200: AutoGasBatchSerializer(many=True),
            404: ApiErrorSerializer
        }
    ),
    create=extend_schema(
        tags=['Автоцистерны'],
        summary='Создать новую партию',
        description='Создание новой партии автоцистерн',
        request=AutoGasBatchSerializer,
        responses={
            201: AutoGasBatchSerializer,
            400: ApiErrorSerializer
        }
    ),
    partial_update=extend_schema(
        tags=['Автоцистерны'],
        summary='Обновить партию',
        description='Частичное обновление данных партии автоцистерн',
        request=AutoGasBatchSerializer,
        responses={
            200: AutoGasBatchSerializer,
            400: ApiErrorSerializer,
            404: ApiErrorSerializer
        }
    )
)
class AutoGasBatchView(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'], url_path='statistic', url_name='statistic')
    def auto_batch_statistic(self, request):
        return Response(get_batch_statistic())

    def list(self, request):
        serializer = AutoGasBatchSerializer(get_today_active_batches(), many=True)
        return Response(serializer.data)

    def create(self, request):
        serializer = AutoGasBatchSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def partial_update(self, request, pk=None):
        batch = get_object_or_404(AutoGasBatch, id=pk)
        serializer = AutoGasBatchSerializer(
            batch,
            data=with_completed_at_on_deactivate(request.data),
            partial=True,
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@receiver(post_save, sender=AutoGasBatch)
@receiver(post_delete, sender=AutoGasBatch)
def clear_auto_gas_cache(sender, **kwargs):
    clear_statistic_cache()
