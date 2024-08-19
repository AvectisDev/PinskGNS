from django.http import HttpRequest, JsonResponse
from .models import Balloon, Truck
from django.views.decorators.csrf import csrf_exempt
import json
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

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
def update_balloon_passport(request: HttpRequest) -> JsonResponse:
    try:
        data = json.loads(request.body.decode('utf-8'))
        nfc = data.get("nfc_tag")
        balloon = Balloon.objects.filter(nfc_tag=nfc).first()

        if not balloon:
            return JsonResponse({'error': 'Balloon not found'}, status=404)

        balloon.serial_number = data.get('serial_number')
        balloon.creation_date = data.get('creation_date')
        balloon.size = data.get('size')
        balloon.netto = data.get('netto')
        balloon.brutto = data.get('brutto')
        balloon.current_examination_date = data.get('current_examination_date')
        balloon.next_examination_date = data.get('next_examination_date')
        balloon.status = data.get('status')

        balloon.save()

        return JsonResponse({'error': 'OK'}, status=200)

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    return JsonResponse({'error': 'Invalid HTTP method'}, status=405)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_balloon_state_options(request):
    try:
        return JsonResponse(USER_STATUS_LIST, safe=False, status=200)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid data'}, status=400)


# @api_view(['GET'])
# @permission_classes([IsAuthenticated])
def get_station_trucks(request):
    try:
        trucks = Truck.objects.filter(is_on_station=True)
        if not trucks:
            return JsonResponse({'error': 'Trucks not found'}, status=404)
        else:
            trucks_list = []
            for truck in trucks:
                trucks_list.append({
                    'car_brand': truck.car_brand,
                    'registration_number': truck.registration_number,
                    'type': truck.type
                })

            return JsonResponse(trucks_list, safe=False, status=200)
    except:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
