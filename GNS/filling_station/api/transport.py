from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.db.models import Sum, Count
from rest_framework import generics, status, viewsets
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from datetime import datetime, date
from ..models import Truck, Trailer
from .serializers import TruckSerializer, TrailerSerializer


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
