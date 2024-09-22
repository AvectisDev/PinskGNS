from ..models import (Balloon, Truck, Trailer, RailwayTank, TTN, BalloonsLoadingBatch, BalloonsUnloadingBatch,
                      RailwayLoadingBatch, GasLoadingBatch, GasUnloadingBatch)
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from datetime import datetime, timedelta
from .serializers import (BalloonSerializer, TruckSerializer, TrailerSerializer, RailwayTanksSerializer, TTNSerializer,
                          BalloonsLoadingBatchSerializer, BalloonsUnloadingBatchSerializer,
                          RailwayLoadingBatchSerializer, GasLoadingBatchSerializer,
                          GasUnloadingBatchSerializer)

USER_STATUS_LIST = [
    'Создание паспорта баллона',
    'Наполнение баллона сжиженным газом',
    'Погрузка пустого баллона в трал',
    'Снятие RFID метки',
    'Установка новой RFID метки',
    'Редактирование паспорта баллона',
    'Покраска',
    'Техническое освидетельствование',
    'Выбраковка',
    'Утечка газа',
    'Опорожнение(слив) баллона',
    'Контрольное взвешивание'
]
BALLOONS_LOADING_READER_LIST = [6]
BALLOONS_UNLOADING_READER_LIST = [3, 4]


class BalloonView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        nfc_tag = request.GET.get('nfc_tag')
        balloon = Balloon.objects.filter(nfc_tag=nfc_tag).first()

        if not balloon:
            return Response(status=status.HTTP_404_NOT_FOUND)

        serializer = BalloonSerializer(balloon)
        return Response(serializer.data)

    def post(self, request):
        serializer = BalloonSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request):
        nfc_tag = request.GET.get('nfc_tag')
        balloon = Balloon.objects.filter(nfc_tag=nfc_tag).first()

        if not balloon:
            return Response(status=status.HTTP_404_NOT_FOUND)
        else:
            serializer = BalloonSerializer(balloon, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
def get_balloon_status_options(request):
    return Response(USER_STATUS_LIST)


@api_view(['GET'])
def get_loading_balloon_reader_list(request):
    return Response(BALLOONS_LOADING_READER_LIST)


@api_view(['GET'])
def get_unloading_balloon_reader_list(request):
    return Response(BALLOONS_UNLOADING_READER_LIST)


class TruckView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.GET.get('on_station') == "True":
            trucks = Truck.objects.filter(is_on_station=True)
        else:
            registration_number = request.GET.get('registration_number')
            trucks = Truck.objects.filter(registration_number=registration_number)

        if not trucks:
            return Response(status=status.HTTP_404_NOT_FOUND)

        serializer = TruckSerializer(trucks, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = TruckSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request):
        truck_id = request.data['id']
        truck = Truck.objects.get(id=truck_id)

        if truck is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        else:
            serializer = TruckSerializer(truck, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class TrailerView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.GET.get('on_station') == "True":
            trailers = Trailer.objects.filter(is_on_station=True)
        else:
            registration_number = request.GET.get('registration_number')
            trailers = Trailer.objects.filter(registration_number=registration_number)

        if not trailers:
            return Response(status=status.HTTP_404_NOT_FOUND)

        serializer = TrailerSerializer(trailers, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = TrailerSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request):
        trailer_id = request.data['id']
        trailer = Trailer.objects.get(id=trailer_id)

        if trailer is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        else:
            serializer = TrailerSerializer(trailer, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class RailwayTanksView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.GET.get('on_station') == "True":
            railway_tanks = RailwayTank.objects.filter(is_on_station=True)
        else:
            number = request.GET.get('number')
            railway_tanks = RailwayTank.objects.filter(number=number)

        if not railway_tanks:
            return Response(status=status.HTTP_404_NOT_FOUND)

        serializer = RailwayTanksSerializer(railway_tanks, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = RailwayTanksSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request):
        railway_tank_id = request.data['id']
        railway_tank = RailwayTank.objects.get(id=railway_tank_id)

        if railway_tank is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        else:
            serializer = RailwayTanksSerializer(railway_tank, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class BalloonsLoadingBatchView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        loading_batches = BalloonsLoadingBatch.objects.filter(is_active=True).first()

        if not loading_batches:
            return Response(status=status.HTTP_404_NOT_FOUND)

        serializer = BalloonsLoadingBatchSerializer(loading_batches)
        return Response(serializer.data)

    def post(self, request):
        serializer = BalloonsLoadingBatchSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request):
        loading_batch = BalloonsLoadingBatch.objects.filter(is_active=True).first()

        if not request.data['is_active']:
            current_date = datetime.now()
            request.data['end_date'] = current_date.date()
            request.data['end_time'] = current_date.time()

        if not loading_batch:
            return Response(status=status.HTTP_404_NOT_FOUND)
        else:
            serializer = BalloonsLoadingBatchSerializer(loading_batch, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class BalloonsUnloadingBatchView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        unloading_batches = BalloonsUnloadingBatch.objects.filter(is_active=True).first()

        if not unloading_batches:
            return Response(status=status.HTTP_404_NOT_FOUND)

        serializer = BalloonsUnloadingBatchSerializer(unloading_batches)
        return Response(serializer.data)

    def post(self, request):
        serializer = BalloonsUnloadingBatchSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request):
        unloading_batch = BalloonsUnloadingBatch.objects.filter(is_active=True).first()

        if not request.data['is_active']:
            current_date = datetime.now()
            request.data['end_date'] = current_date.date()
            request.data['end_time'] = current_date.time()

        if not unloading_batch:
            return Response(status=status.HTTP_404_NOT_FOUND)
        else:
            serializer = BalloonsUnloadingBatchSerializer(unloading_batch, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class RailwayLoadingBatchView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        batches = RailwayLoadingBatch.objects.filter(is_active=True).first()

        if not batches:
            return Response(status=status.HTTP_404_NOT_FOUND)

        serializer = RailwayLoadingBatchSerializer(batches)
        return Response(serializer.data)

    def post(self, request):
        serializer = RailwayLoadingBatchSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request):
        batch = RailwayLoadingBatch.objects.filter(is_active=True).first()

        if not request.data['is_active']:
            current_date = datetime.now()
            request.data['end_date'] = current_date.date()
            request.data['end_time'] = current_date.time()

        if not batch:
            return Response(status=status.HTTP_404_NOT_FOUND)
        else:
            serializer = RailwayLoadingBatchSerializer(batch, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class GasLoadingBatchView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        loading_batches = GasLoadingBatch.objects.filter(is_active=True).first()

        if not loading_batches:
            return Response(status=status.HTTP_404_NOT_FOUND)

        serializer = GasLoadingBatchSerializer(loading_batches)
        return Response(serializer.data)

    def post(self, request):
        serializer = GasLoadingBatchSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request):
        loading_batches = GasLoadingBatch.objects.filter(is_active=True).first()

        if not request.data['is_active']:
            current_date = datetime.now()
            request.data['end_date'] = current_date.date()
            request.data['end_time'] = current_date.time()

        if not loading_batches:
            return Response(status=status.HTTP_404_NOT_FOUND)
        else:
            serializer = GasLoadingBatchSerializer(loading_batches, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class GasUnloadingBatchView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        unloading_batches = GasUnloadingBatch.objects.filter(is_active=True).first()

        if not unloading_batches:
            return Response(status=status.HTTP_404_NOT_FOUND)

        serializer = GasUnloadingBatchSerializer(unloading_batches)
        return Response(serializer.data)

    def post(self, request):
        serializer = GasUnloadingBatchSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request):
        unloading_batches = GasUnloadingBatch.objects.filter(is_active=True).first()

        if not request.data['is_active']:
            current_date = datetime.now()
            request.data['end_date'] = current_date.date()
            request.data['end_time'] = current_date.time()

        if not unloading_batches:
            return Response(status=status.HTTP_404_NOT_FOUND)
        else:
            serializer = GasUnloadingBatchSerializer(unloading_batches, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
