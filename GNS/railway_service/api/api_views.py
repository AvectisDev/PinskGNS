from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.db.models import Sum, Count, Value, Case, When, IntegerField, DecimalField
from django.db.models.functions import Coalesce
from django.core.cache import cache
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from rest_framework import generics, status, viewsets, serializers
from rest_framework.response import Response
from rest_framework.decorators import api_view, action
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import (
    extend_schema,
    extend_schema_view,
    inline_serializer,
    OpenApiTypes,
    OpenApiExample
)
from datetime import datetime, date
from railway_service.models import RailwayTank, RailwayBatch, RailwayTankHistory
from .serializers import RailwayBatchSerializer
from core.api.schema import ApiErrorSerializer


@extend_schema_view(
    statistic=extend_schema(
        tags=['Железнодорожные партии'],
        summary='Получить статистику по железнодорожным партиям',
        description='Получение сводной статистики по железнодорожным цистернам и партиям. '
                    'Включает статистику за последний месяц и за сегодня, а также информацию о цистернах на станции.',
        responses={
            200: OpenApiTypes.OBJECT
        },
        examples=[
            OpenApiExample(
                'Пример ответа',
                value={
                    'loading_batch': {
                        'last_month_total_tanks_spbt': 10,
                        'last_month_total_tanks_pba': 5,
                        'last_month_gas_amount_spbt': 150000.50,
                        'last_month_gas_amount_pba': 75000.25,
                        'last_day_total_tanks_spbt': 2,
                        'last_day_total_tanks_pba': 1,
                        'last_day_gas_amount_spbt': 30000.00,
                        'last_day_gas_amount_pba': 15000.00
                    },
                    '1234567': {
                        'registration_number': '1234567',
                        'gas_type': 'СПБТ',
                        'full_weight': 85000.50
                    }
                },
                response_only=True
            )
        ]
    ),
    list=extend_schema(
        tags=['Железнодорожные партии'],
        summary='Получить активную партию',
        description='Получение данных активной железнодорожной партии',
        responses={
            200: RailwayBatchSerializer,
            404: ApiErrorSerializer
        }
    ),
    create=extend_schema(
        tags=['Железнодорожные партии'],
        summary='Создать новую партию',
        description='Создание новой железнодорожной партии',
        request=RailwayBatchSerializer,
        responses={
            201: RailwayBatchSerializer,
            400: ApiErrorSerializer
        }
    ),
    partial_update=extend_schema(
        tags=['Железнодорожные партии'],
        summary='Обновить партию',
        description='Частичное обновление данных железнодорожной партии',
        request=RailwayBatchSerializer,
        responses={
            200: RailwayBatchSerializer,
            400: ApiErrorSerializer,
            404: ApiErrorSerializer
        }
    )
)
class RailwayBatchView(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'], url_path='statistic')
    def railway_batch_statistic(self, request):
        cache_key = 'railway_batch_statistic'
        cached_data = cache.get(cache_key)

        if cached_data is not None:
            return JsonResponse(cached_data, safe=False)

        today = date.today()
        first_day_of_month = today.replace(day=1)
        
        # Начало и конец дня для фильтрации
        today_start = datetime.combine(today, datetime.min.time())
        today_end = datetime.combine(today, datetime.max.time())
        month_start = datetime.combine(first_day_of_month, datetime.min.time())

        response = {}
        
        # Статистика за последний месяц (фильтруем по departure_at, т.к. данные формируются при выезде)
        month_history = RailwayTankHistory.objects.filter(
            departure_at__gte=month_start,
            departure_at__isnull=False
        )
        
        # Подсчет уникальных цистерн за месяц
        month_tanks_spbt = month_history.filter(gas_type='СПБТ').values('tank').distinct().count()
        month_tanks_pba = month_history.filter(gas_type='ПБА').values('tank').distinct().count()
        
        # Подсчет количества газа за месяц
        month_gas_stats = month_history.aggregate(
            last_month_gas_amount_spbt=Coalesce(
                Sum(
                    Case(
                        When(gas_type='СПБТ', then='gas_weight'),
                        output_field=DecimalField(max_digits=12, decimal_places=2)
                    ),
                    output_field=DecimalField(max_digits=12, decimal_places=2)
                ),
                Value(0.0),
                output_field=DecimalField(max_digits=12, decimal_places=2)
            ),
            last_month_gas_amount_pba=Coalesce(
                Sum(
                    Case(
                        When(gas_type='ПБА', then='gas_weight'),
                        output_field=DecimalField(max_digits=12, decimal_places=2)
                    ),
                    output_field=DecimalField(max_digits=12, decimal_places=2)
                ),
                Value(0.0),
                output_field=DecimalField(max_digits=12, decimal_places=2)
            )
        )
        
        # Статистика за последний день (фильтруем по departure_at)
        day_history = RailwayTankHistory.objects.filter(
            departure_at__gte=today_start,
            departure_at__lte=today_end,
            departure_at__isnull=False
        )
        
        # Подсчет уникальных цистерн за день
        day_tanks_spbt = day_history.filter(gas_type='СПБТ').values('tank').distinct().count()
        day_tanks_pba = day_history.filter(gas_type='ПБА').values('tank').distinct().count()
        
        # Подсчет количества газа за день
        day_gas_stats = day_history.aggregate(
            last_day_gas_amount_spbt=Coalesce(
                Sum(
                    Case(
                        When(gas_type='СПБТ', then='gas_weight'),
                        output_field=DecimalField(max_digits=12, decimal_places=2)
                    ),
                    output_field=DecimalField(max_digits=12, decimal_places=2)
                ),
                Value(0.0),
                output_field=DecimalField(max_digits=12, decimal_places=2)
            ),
            last_day_gas_amount_pba=Coalesce(
                Sum(
                    Case(
                        When(gas_type='ПБА', then='gas_weight'),
                        output_field=DecimalField(max_digits=12, decimal_places=2)
                    ),
                    output_field=DecimalField(max_digits=12, decimal_places=2)
                ),
                Value(0.0),
                output_field=DecimalField(max_digits=12, decimal_places=2)
            )
        )
        
        # Объединяем статистику
        response['loading_batch'] = {
            'last_month_total_tanks_spbt': month_tanks_spbt,
            'last_month_total_tanks_pba': month_tanks_pba,
            'last_month_gas_amount_spbt': month_gas_stats['last_month_gas_amount_spbt'],
            'last_month_gas_amount_pba': month_gas_stats['last_month_gas_amount_pba'],
            'last_day_total_tanks_spbt': day_tanks_spbt,
            'last_day_total_tanks_pba': day_tanks_pba,
            'last_day_gas_amount_spbt': day_gas_stats['last_day_gas_amount_spbt'],
            'last_day_gas_amount_pba': day_gas_stats['last_day_gas_amount_pba'],
        }

        # Цистерны на станции
        tanks_on_station = RailwayTank.objects.filter(is_on_station=True).prefetch_related('tank_history')
        for tank in tanks_on_station:
            last_history = tank.tank_history.first()  # first() потому что ordering = ['-arrival_at']
            response[tank.registration_number] = {
                'registration_number': tank.registration_number,
                'gas_type': last_history.gas_type if last_history else 'Не выбран',
                'full_weight': float(last_history.full_weight) if last_history and last_history.full_weight else 0
            }
        
        # Сохраняем в кеш на 1 час
        cache.set(cache_key, response, timeout=3600)
        return JsonResponse(response, safe=False)

    def list(self, request):
        batches = RailwayBatch.objects.filter(is_active=True).first()

        if not batches:
            return Response(status=status.HTTP_404_NOT_FOUND)

        serializer = RailwayBatchSerializer(batches)
        return Response(serializer.data)

    def create(self, request):
        serializer = RailwayBatchSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def partial_update(self, request, pk=None):
        batch = get_object_or_404(RailwayBatch, id=pk)

        if not request.data.get('is_active', True):
            request.data['end_date'] = datetime.now()

        serializer = RailwayBatchSerializer(batch, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# Сигналы для сброса кеша при изменении данных
@receiver(post_save, sender=RailwayTankHistory)
@receiver(post_delete, sender=RailwayTankHistory)
@receiver(post_save, sender=RailwayTank)
@receiver(post_delete, sender=RailwayTank)
def clear_railway_statistic_cache(sender, **kwargs):
    """Сбрасывает кеш статистики при изменении истории цистерн или самих цистерн"""
    cache.delete('railway_batch_statistic')
