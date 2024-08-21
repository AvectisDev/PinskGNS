from django.http import HttpRequest, JsonResponse
from .models import Balloon, Truck, LoadingBatchBalloons
import json
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from datetime import datetime, timedelta

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


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_balloon_passport(request):
    try:
        nfc = request.GET.get("nfc", 0)
        balloon = Balloon.objects.filter(nfc_tag=nfc).last()
        if not balloon:
            return JsonResponse({'error': 'Balloon not found'}, status=404)
        else:
            return JsonResponse({
                'nfc_tag': balloon.nfc_tag,
                'serial_number': balloon.serial_number,
                'creation_date': balloon.creation_date,
                'size': balloon.size,
                'netto': balloon.netto,
                'brutto': balloon.brutto,
                'current_examination_date': balloon.current_examination_date,
                'next_examination_date': balloon.next_examination_date,
                'status': balloon.status}
            )
    except:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_balloon_passport(request):
    try:
        data = json.loads(request.body.decode('utf-8'))
        nfc = data.get("nfc_tag")
        balloon = Balloon.objects.filter(nfc_tag=nfc).last()

        if not balloon:
            return Response({'error': 'Balloon not found'})

        balloon.serial_number = data.get('serial_number')
        balloon.creation_date = data.get('creation_date')
        balloon.size = data.get('size')
        balloon.netto = data.get('netto')
        balloon.brutto = data.get('brutto')
        balloon.current_examination_date = data.get('current_examination_date')
        balloon.next_examination_date = data.get('next_examination_date')
        balloon.status = data.get('status')

        balloon.save()

        return Response({'error': 'OK'})

    except json.JSONDecodeError:
        return Response({'error': 'Invalid JSON'})

    return Response({'error': 'Invalid HTTP method'})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_balloon_state_options(request):
    try:
        return Response(USER_STATUS_LIST)
    except json.JSONDecodeError:
        return Response({'error': 'Invalid data'})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_station_trucks(request):
    try:
        trucks = Truck.objects.filter(is_on_station=True)
        if not trucks:
            return Response({'error': 'Trucks not found'})
        else:
            trucks_list = []
            for truck in trucks:
                trucks_list.append({
                    'car_brand': truck.car_brand,
                    'registration_number': truck.registration_number,
                    'type': truck.type
                })

            return Response(trucks_list)
    except:
        return Response({'error': 'Invalid JSON'})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def start_loading(request):
    try:
        truck_registration_number = json.loads(request.body.decode())
        if not truck_registration_number:
            return Response({'status': 'Trucks not found'})
        else:
            shipping_batch = LoadingBatchBalloons()
            truck = Truck.objects.get(registration_number=truck_registration_number['registration_number']).__dict__
            current_date = datetime.now()
            shipping_batch.begin_date = current_date.date()
            shipping_batch.begin_time = current_date.time()
            shipping_batch.truck_id = truck['id']
            shipping_batch.is_active = True

            shipping_batch.save()

            return Response({'status': 'ok'})
    except json.JSONDecodeError:
        return Response({'error': 'Invalid JSON'})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def stop_loading(request):
    try:
        batch_data = json.loads(request.body.decode())
        if not batch_data:
            return Response({'status': 'error'})
        else:
            loading_batch = LoadingBatchBalloons.objects.last()
            current_date = datetime.now()
            loading_batch.amount_of_5_liters = batch_data['amount_of_5_liters']
            loading_batch.amount_of_20_liters = batch_data['amount_of_20_liters']
            loading_batch.amount_of_50_liters = batch_data['amount_of_50_liters']
            loading_batch.end_date = current_date.date()
            loading_batch.end_time = current_date.time()
            loading_batch.is_active = False

            loading_batch.save()

            return Response({'status': 'ok'})
    except json.JSONDecodeError:
        return Response({'error': 'Invalid JSON'})

@api_view(['GET'])
def get_loading_batch_balloons(request):
    try:
        loading_batch_balloons = LoadingBatchBalloons.objects.filter(is_active=True).last().__dict__
        if not loading_batch_balloons:
            return Response({'status': 'error', 'error': 'loading batch not found'})
        else:
            return Response({'status': 'ok', 'loading_batch_id': loading_batch_balloons['id']})
    except:
        return Response({'status': 'error', 'error': 'Invalid JSON'})


@api_view(['POST'])
def update_loading_batch_balloons(request):
    try:
        data = json.loads(request.body.decode())
        if not data:
            return Response({'status': 'error', 'error': 'loading batch not found'})
        else:
            loading_batch = LoadingBatchBalloons.objects.get(id=data['loading_batch_id'])
            loading_batch.balloons_list = data['balloons_list']
            loading_batch.save()
            return Response({'status': 'ok'})
    except:
        return Response({'status': 'error', 'error': 'Invalid JSON'})
