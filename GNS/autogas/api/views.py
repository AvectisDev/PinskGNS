from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.db.models import Sum, Count
from django.core.cache import cache
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from rest_framework import generics, status, viewsets
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny
from datetime import datetime, date
from autogas.models import AutoGasBatch
from .serializers import AutoGasBatchSerializer


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
        active_batch = AutoGasBatch.objects.filter(is_active=True).first()
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
                # ttn данные исключены, так как нет связанного поля
            }

        cache.set(cache_key, response)
        return JsonResponse(response, safe=False)

    def list(self, request):
        today = date.today()
        batch = AutoGasBatch.objects.filter(is_active=True, begin_at__date=today)
        serializer = AutoGasBatchSerializer(batch, many=True)
        return Response(serializer.data)

    def create(self, request):
        serializer = AutoGasBatchSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors)

    def partial_update(self, request, pk=None):
        batch = get_object_or_404(AutoGasBatch, id=pk)
        if not request.data.get('is_active', True):
            request.data['completed_at'] = datetime.now()
        serializer = AutoGasBatchSerializer(batch, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors)

# Сигналы для сброса кеша при изменении данных
@receiver(post_save, sender=AutoGasBatch)
@receiver(post_delete, sender=AutoGasBatch)
def clear_auto_gas_cache(sender, **kwargs):
    cache.delete('auto_gas_batch_statistic')
