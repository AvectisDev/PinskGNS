from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.db.models import Sum, Count
from rest_framework import generics, status, viewsets
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from datetime import datetime, date
from ..models import Truck, Trailer, AutoGasBatch
from .serializers import TruckSerializer, TrailerSerializer, AutoGasBatchSerializer


class TruckView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        on_station = request.query_params.get('on_station', False)
        registration_number = request.query_params.get('registration_number', False)

        if on_station:
            # trucks = Truck.objects.filter(is_on_station=True)
            trucks = Truck.objects.all()
            if not trucks:
                return Response(status=status.HTTP_404_NOT_FOUND)
            serializer = TruckSerializer(trucks, many=True)
            return Response(serializer.data)

        if registration_number:
            trucks = get_object_or_404(Truck, registration_number=registration_number)
            serializer = TruckSerializer(trucks)
            return Response(serializer.data)

    def post(self, request):
        serializer = TruckSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request):
        truck_id = request.data['id']
        truck = get_object_or_404(Truck, id=truck_id)

        serializer = TruckSerializer(truck, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class TrailerView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        on_station = request.query_params.get('on_station', False)
        registration_number = request.query_params.get('registration_number', False)

        if on_station:
            # trailers = Trailer.objects.filter(is_on_station=True)
            trailers = Trailer.objects.all()
            if not trailers:
                return Response(status=status.HTTP_404_NOT_FOUND)
            serializer = TrailerSerializer(trailers, many=True)
            return Response(serializer.data)

        if registration_number:
            trailer = get_object_or_404(Trailer, registration_number=registration_number)
            serializer = TrailerSerializer(trailer)
            return Response(serializer.data)

    def post(self, request):
        serializer = TrailerSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request):
        trailer_id = request.data['id']
        trailer = get_object_or_404(Trailer, id=trailer_id)

        serializer = TrailerSerializer(trailer, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AutoGasBatchView(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'], url_path='statistic')
    def auto_batch_statistic(self, request):
        today = date.today()
        first_day_of_month = today.replace(day=1)

        result = []
        # Партии за последний месяц
        result.append(AutoGasBatch.objects
                      .filter(begin_date__gte=first_day_of_month, batch_type='l', gas_type='ПБА')
                      .values('gas_type', 'batch_type')
                      .annotate(last_month_loading_batches=Count('id'),
                                last_month_loading_weight=Sum('weight_gas_amount')))
        result.append(AutoGasBatch.objects
                      .filter(begin_date__gte=first_day_of_month, batch_type='l', gas_type='СПБТ')
                      .values('gas_type', 'batch_type')
                      .annotate(last_month_loading_batches=Count('id'),
                                last_month_loading_weight=Sum('weight_gas_amount')))
        result.append(AutoGasBatch.objects
                      .filter(begin_date__gte=first_day_of_month, batch_type='u', gas_type='ПБА')
                      .values('gas_type', 'batch_type')
                      .annotate(last_month_unloading_batches=Count('id'),
                                last_month_unloading_weight=Sum('weight_gas_amount')))
        result.append(AutoGasBatch.objects
                      .filter(begin_date__gte=first_day_of_month, batch_type='u',
                              gas_type='СПБТ')
                      .values('gas_type', 'batch_type')
                      .annotate(last_month_unloading_batches=Count('id'),
                                last_month_unloading_weight=Sum('weight_gas_amount')))

        # Партии за последний день
        result.append(AutoGasBatch.objects
                      .filter(begin_date=today, batch_type='l', gas_type='ПБА')
                      .values('gas_type', 'batch_type')
                      .annotate(today_loading_batches=Count('id'),
                                today_loading_weight=Sum('weight_gas_amount')))
        result.append(AutoGasBatch.objects
                      .filter(begin_date=today, batch_type='l', gas_type='СПБТ')
                      .values('gas_type', 'batch_type')
                      .annotate(today_loading_batches=Count('id'),
                                today_loading_weight=Sum('weight_gas_amount')))
        result.append(AutoGasBatch.objects
                      .filter(begin_date=today, batch_type='u', gas_type='ПБА')
                      .values('gas_type', 'batch_type')
                      .annotate(today_unloading_batches=Count('id'),
                                today_unloading_weight=Sum('weight_gas_amount')))
        result.append(AutoGasBatch.objects
                      .filter(begin_date=today, batch_type='u', gas_type='СПБТ')
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
                'ttn_number': active_batch.ttn.number if active_batch.ttn else None,
                'ttn_consignee': active_batch.ttn.consignee if active_batch.ttn else None
            }
        return JsonResponse(response, safe=False)

    def list(self, request):
        today = date.today()
        batch = AutoGasBatch.objects.filter(is_active=True, begin_date=today)
        serializer = AutoGasBatchSerializer(batch)
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
            current_date = datetime.now()
            request.data['end_date'] = current_date.date()
            request.data['end_time'] = current_date.time()

        serializer = AutoGasBatchSerializer(batch, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors)
