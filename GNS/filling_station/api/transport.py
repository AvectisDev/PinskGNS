from ..models import (Truck, Trailer, RailwayTank,
                      RailwayBatch, AutoGasBatch)
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.db.models import Sum, Count, Value, Case, When, IntegerField
from django.db.models.functions import Coalesce
from rest_framework import generics, status, viewsets
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import api_view, action
from rest_framework.permissions import IsAuthenticated
from datetime import datetime, date
from .serializers import (TruckSerializer, TrailerSerializer, RailwayTankSerializer,
                          RailwayBatchSerializer, AutoGasBatchSerializer)


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


class RailwayTankView(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['post'], url_path='update')
    def update_railway_tank(self, request):
        current_date = datetime.now().date()
        current_time = datetime.now().time()

        registration_number = request.data.get('registration_number', None)
        is_on_station = request.data.get('is_on_station', False)
        tank_weight = request.data.get('tank_weight', 0.0)

        railway_tank, created = RailwayTank.objects.get_or_create(
            registration_number=registration_number,
            defaults={
                'registration_number': registration_number,
                'is_on_station': is_on_station,
                'entry_date': current_date if is_on_station else None,
                'entry_time': current_time if is_on_station else None,
                'departure_date': current_date if not is_on_station else None,
                'departure_time': current_time if not is_on_station else None,
                'full_weight': tank_weight if is_on_station else None,
                'empty_weight': tank_weight if not is_on_station else None,
            }
        )

        if not created:
            railway_tank.is_on_station = is_on_station
            if is_on_station:
                railway_tank.entry_date = current_date
                railway_tank.entry_time = current_time
                railway_tank.full_weight = tank_weight
            else:
                railway_tank.departure_date = current_date
                railway_tank.departure_time = current_time
                railway_tank.empty_weight = tank_weight
                railway_tank.gas_weight = railway_tank.full_weight or 0 - tank_weight
            railway_tank.save()

        return Response(status=status.HTTP_200_OK)

    def create(self, request):
        serializer = RailwayTankSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def partial_update(self, request, pk=None):
        railway_tank = get_object_or_404(RailwayTank, id=pk)

        serializer = RailwayTankSerializer(railway_tank, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class RailwayBatchView(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'], url_path='statistic')
    def railway_batch_statistic(self, request):
        today = date.today()
        first_day_of_month = today.replace(day=1)

        result = []
        # Партии за последний месяц
        result.append(RailwayBatch.objects
        .filter(begin_date__gte=first_day_of_month)
        .aggregate(
            last_month_total_tanks_spbt=Count(Case(
                When(railway_tank_list__gas_type='СПБТ', then=1),
                output_field=IntegerField()
            )),
            last_month_total_tanks_pba=Count(Case(
                When(railway_tank_list__gas_type='ПБА', then=1),
                output_field=IntegerField()
            )),
            last_month_gas_amount_spbt=Coalesce(Sum('gas_amount_spbt'), Value(0.0)),
            last_month_gas_amount_pba=Coalesce(Sum('gas_amount_pba'), Value(0.0)))
        )

        # Партии за последний день
        result.append(RailwayBatch.objects
        .filter(begin_date=today)
        .aggregate(last_day_total_tanks_spbt=Count(Case(
            When(railway_tank_list__gas_type='СПБТ', then=1),
            output_field=IntegerField()
        )),
            last_day_total_tanks_pba=Count(Case(
                When(railway_tank_list__gas_type='ПБА', then=1),
                output_field=IntegerField()
            )),
            last_day_gas_amount_spbt=Coalesce(Sum('gas_amount_spbt'), Value(0.0)),
            last_day_gas_amount_pba=Coalesce(Sum('gas_amount_pba'), Value(0.0)))
        )

        response = {}
        for item in result:
            response['loading_batch'] = response.get('loading_batch', {}) | item

        # Активная партия
        tanks_on_station = RailwayTank.objects.filter(is_on_station=True)
        for tank in tanks_on_station:
            response[tank.registration_number] = {
                'registration_number': tank.registration_number,
                'gas_type': tank.gas_type,
                'full_weight': tank.full_weight if tank.full_weight else 0
            }
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
            current_date = datetime.now()
            request.data['end_date'] = current_date.date()
            request.data['end_time'] = current_date.time()

        serializer = RailwayBatchSerializer(batch, data=request.data, partial=True)
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
                'trailer_number': active_batch.trailer.registration_number,
                'truck_gas_capacity': active_batch.truck.max_gas_volume if active_batch.truck.max_gas_volume else 0,
                'scale_empty_weight': active_batch.scale_empty_weight if active_batch.scale_empty_weight else 0,
                'scale_full_weight': active_batch.scale_full_weight if active_batch.scale_full_weight else 0,
                'ttn_number': active_batch.ttn.number,
                'ttn_consignee': active_batch.ttn.consignee,
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
