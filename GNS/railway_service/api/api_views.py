from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.db.models import Sum, Count, Value, Case, When, IntegerField, DecimalField
from django.db.models.functions import Coalesce
from rest_framework import generics, status, viewsets
from rest_framework.response import Response
from rest_framework.decorators import api_view, action
from rest_framework.permissions import IsAuthenticated
from datetime import datetime, date
from railway_service.models import RailwayTank, RailwayBatch
from .serializers import RailwayBatchSerializer


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
            last_month_gas_amount_spbt=Coalesce(
                Sum('gas_amount_spbt', output_field=DecimalField(max_digits=12, decimal_places=2)),
                Value(0.0),
                output_field=DecimalField(max_digits=12, decimal_places=2)
            ),
            last_month_gas_amount_pba=Coalesce(
                Sum('gas_amount_pba', output_field=DecimalField(max_digits=12, decimal_places=2)),
                Value(0.0),
                output_field=DecimalField(max_digits=12, decimal_places=2)
            ))
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
            last_day_gas_amount_spbt=Coalesce(
                Sum('gas_amount_spbt', output_field=DecimalField(max_digits=12, decimal_places=2)),
                Value(0.0),
                output_field=DecimalField(max_digits=12, decimal_places=2)
            ),
            last_day_gas_amount_pba=Coalesce(
                Sum('gas_amount_pba', output_field=DecimalField(max_digits=12, decimal_places=2)),
                Value(0.0),
                output_field=DecimalField(max_digits=12, decimal_places=2)
            ))
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
            request.data['end_date'] = datetime.now()

        serializer = RailwayBatchSerializer(batch, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
