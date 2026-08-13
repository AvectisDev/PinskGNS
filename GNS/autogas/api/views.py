from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.db.models import Sum, Count
from django.core.cache import cache
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from rest_framework import generics, status, viewsets, serializers
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
from datetime import date
from django.utils import timezone
from autogas.models import AutoGasBatch
from .serializers import AutoGasBatchSerializer


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
            404: OpenApiTypes.OBJECT
        }
    ),
    create=extend_schema(
        tags=['Автоцистерны'],
        summary='Создать новую партию',
        description='Создание новой партии автоцистерн',
        request=AutoGasBatchSerializer,
        responses={
            201: AutoGasBatchSerializer,
            400: OpenApiTypes.OBJECT
        }
    ),
    partial_update=extend_schema(
        tags=['Автоцистерны'],
        summary='Обновить партию',
        description='Частичное обновление данных партии автоцистерн',
        request=AutoGasBatchSerializer,
        responses={
            200: AutoGasBatchSerializer,
            400: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT
        }
    )
)
class AutoGasBatchView(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'], url_path='statistic')
    def auto_batch_statistic(self, request):
        cache_key = 'auto_gas_batch_statistic'
        cached_data = cache.get(cache_key)

        if cached_data is not None:
            return JsonResponse(cached_data, safe=False)

        today = date.today()
        first_day_of_month = today.replace(day=1)

        result = []
        # Партии за последний месяц
        result.append(AutoGasBatch.objects
                      .filter(begin_at__date__gte=first_day_of_month, batch_type='l', gas_type='ПБА')
                      .values('gas_type', 'batch_type')
                      .annotate(last_month_loading_batches=Count('id'),
                                last_month_loading_weight=Sum('weight_gas_amount')))
        result.append(AutoGasBatch.objects
                      .filter(begin_at__date__gte=first_day_of_month, batch_type='l', gas_type='СПБТ')
                      .values('gas_type', 'batch_type')
                      .annotate(last_month_loading_batches=Count('id'),
                                last_month_loading_weight=Sum('weight_gas_amount')))
        result.append(AutoGasBatch.objects
                      .filter(begin_at__date__gte=first_day_of_month, batch_type='u', gas_type='ПБА')
                      .values('gas_type', 'batch_type')
                      .annotate(last_month_unloading_batches=Count('id'),
                                last_month_unloading_weight=Sum('weight_gas_amount')))
        result.append(AutoGasBatch.objects
                      .filter(begin_at__date__gte=first_day_of_month, batch_type='u',
                              gas_type='СПБТ')
                      .values('gas_type', 'batch_type')
                      .annotate(last_month_unloading_batches=Count('id'),
                                last_month_unloading_weight=Sum('weight_gas_amount')))

        # Партии за последний день
        result.append(AutoGasBatch.objects
                      .filter(begin_at__date=today, batch_type='l', gas_type='ПБА')
                      .values('gas_type', 'batch_type')
                      .annotate(today_loading_batches=Count('id'),
                                today_loading_weight=Sum('weight_gas_amount')))
        result.append(AutoGasBatch.objects
                      .filter(begin_at__date=today, batch_type='l', gas_type='СПБТ')
                      .values('gas_type', 'batch_type')
                      .annotate(today_loading_batches=Count('id'),
                                today_loading_weight=Sum('weight_gas_amount')))
        result.append(AutoGasBatch.objects
                      .filter(begin_at__date=today, batch_type='u', gas_type='ПБА')
                      .values('gas_type', 'batch_type')
                      .annotate(today_unloading_batches=Count('id'),
                                today_unloading_weight=Sum('weight_gas_amount')))
        result.append(AutoGasBatch.objects
                      .filter(begin_at__date=today, batch_type='u', gas_type='СПБТ')
                      .values('gas_type', 'batch_type')
                      .annotate(today_unloading_batches=Count('id'),
                                today_unloading_weight=Sum('weight_gas_amount')))

        response = {'loading_batch': {}, 'unloading_batch': {}}
        for item in result:
            for r in item:
                if r['batch_type'] == 'l':
                    if r['gas_type'] == 'ПБА':
                        response['loading_batch']['ПБА'] = response.get('loading_batch', {}).get('ПБА', {}) | r
                    else:
                        response['loading_batch']['СПБТ'] = response.get('loading_batch', {}).get('СПБТ', {}) | r
                else:
                    if r['gas_type'] == 'ПБА':
                        response['unloading_batch']['ПБА'] = response.get('unloading_batch', {}).get('ПБА', {}) | r
                    else:
                        response['unloading_batch']['СПБТ'] = response.get('unloading_batch', {}).get('СПБТ', {}) | r

        # Активная партия
        active_batch = (
            AutoGasBatch.objects
            .select_related('truck', 'trailer')
            .filter(is_active=True)
            .first()
        )
        if active_batch:
            response['active_batch'] = {
                'batch_type': 'Приёмка' if active_batch.batch_type == 'l' else 'Отгрузка',
                'gas_type': active_batch.gas_type,
                'car_brand': active_batch.truck.car_brand,
                'truck_number': active_batch.truck.registration_number,
                'trailer_number': active_batch.trailer.registration_number if active_batch.trailer else None,
                'truck_gas_capacity': active_batch.truck.max_gas_volume if active_batch.truck.max_gas_volume else 0,
                'scale_empty_weight': active_batch.scale_empty_weight if active_batch.scale_empty_weight else 0,
                'scale_full_weight': active_batch.scale_full_weight if active_batch.scale_full_weight else 0,
            }

        cache.set(cache_key, response)
        return JsonResponse(response, safe=False)

    def list(self, request):
        today = date.today()
        batches = AutoGasBatch.objects.filter(
            is_active=True,
            begin_at__date=today,
        ).select_related('truck', 'trailer')
        serializer = AutoGasBatchSerializer(batches, many=True)
        return Response(serializer.data)

    def create(self, request):
        serializer = AutoGasBatchSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def partial_update(self, request, pk=None):
        batch = get_object_or_404(AutoGasBatch, id=pk)
        data = request.data.copy()
        if not data.get('is_active', True):
            data['completed_at'] = timezone.now()
        serializer = AutoGasBatchSerializer(batch, data=data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# Сигналы для сброса кеша при изменении данных
@receiver(post_save, sender=AutoGasBatch)
@receiver(post_delete, sender=AutoGasBatch)
def clear_auto_gas_cache(sender, **kwargs):
    cache.delete('auto_gas_batch_statistic')
