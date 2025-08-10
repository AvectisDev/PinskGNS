import logging
from django.http import JsonResponse
from django.db.models import Q, Sum, Count
from django.shortcuts import get_object_or_404
from django.core.cache import cache
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from rest_framework import generics, status, viewsets, serializers
from rest_framework.response import Response
from rest_framework.decorators import api_view, action
from rest_framework.permissions import IsAuthenticated, AllowAny
from drf_spectacular.utils import (
    extend_schema,
    OpenApiParameter,
    OpenApiExample,
    OpenApiTypes,
    extend_schema_view,
    inline_serializer
)
from datetime import datetime, date
from ..models import Balloon, Reader, BalloonsLoadingBatch, BalloonsUnloadingBatch, ReaderSettings
from .serializers import (
    BalloonSerializer,
    BalloonsLoadingBatchSerializer,
    BalloonsUnloadingBatchSerializer,
    ActiveLoadingBatchSerializer,
    ActiveUnloadingBatchSerializer,
    BalloonAmountLoadingSerializer,
    BalloonAmountUnloadingSerializer
)
from .. import services


logger = logging.getLogger('filling_station')

USER_STATUS_LIST = [
    'Создание паспорта баллона',
    'Наполнение баллона сжиженным газом',
    'Погрузка полного баллона в кассету',
    'Погрузка полного баллона в трал',
    'Погрузка пустого баллона в кассету',
    'Погрузка пустого баллона в трал',
    'Регистрация полного баллона на складе',
    'Регистрация пустого баллона на складе',
    'Снятие пустого баллона у потребителя',
    'Установка баллона потребителю',
    'Принятие баллона от другой организации',
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
BALLOONS_LOADING_READER_LIST = [1, 6]
BALLOONS_UNLOADING_READER_LIST = [2, 3, 4]


class BalloonViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger = logging.getLogger(__name__)

    @action(detail=False, methods=['get'], url_path='nfc/(?P<nfc_tag>[^/.]+)')
    def get_by_nfc(self, request, nfc_tag=None):
        balloon = get_object_or_404(Balloon, nfc_tag=nfc_tag)
        serializer = BalloonSerializer(balloon)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='serial-number/(?P<serial_number>[^/.]+)')
    def get_by_serial_number(self, request, serial_number=None):
        balloons = Balloon.objects.filter(serial_number=serial_number)
        serializer = BalloonSerializer(balloons, many=True)
        return Response(serializer.data)


    @action(detail=False, methods=['post'], url_path='update-by-reader')
    def update_by_reader(self, request):
        """
        Метод для обновления данных баллона по NFC-метке. Если у баллона активен флаг "обновление паспорта", то
        повторно запрашиваем данные в Мириаде через метод get_balloon_by_nfc_tag
        """
        reader_number = request.data.get('reader_number')
        if reader_number is None:
            self.logger.error("Номер ридера отсутствует в теле запроса")
            return Response({"error": "Номер считывателя отсутствует в теле запроса"}, status=400)

        nfc_tag = request.data.get('nfc_tag')
        # Ситуация, когда нет метки
        if nfc_tag is None:
            services.processing_request_without_nfc(reader_number)
            return Response(status=200)

        # Ситуация, когда есть метка
        balloon, reader = services.processing_request_with_nfc(nfc_tag=nfc_tag, reader_number=reader_number)

        # Отправка статусов в Мириаду
        if (2 <= reader.number <= 6) or reader.number == 8:
            services.send_status_to_miriada(reader=reader.number, nfc_tag=balloon.nfc_tag)

        serializer = BalloonSerializer(balloon)
        return Response(serializer.data)


    @action(detail=False, methods=['get'], url_path='statistic')
    def get_statistic(self, request):
        cache_key = 'get_balloon_statistic'
        cache_time = 600  # 10 минут
        data = cache.get(cache_key)

        if not data:
            today = date.today()
            first_day_of_month = today.replace(day=1)

            # Баллонов на станции
            filled_balloons_on_station = (Balloon.objects
                                          .filter(status='Регистрация полного баллона на складе')
                                          .aggregate(total=Count('nfc_tag')))
            empty_balloons_on_station = (Balloon.objects
                                         .filter(status__in=['Регистрация пустого баллона на складе (рампа)',
                                                             'Регистрация пустого баллона на складе (цех)'])
                                         .aggregate(total=Count('nfc_tag')))

            # Баллонов за текущий месяц
            balloons_monthly_stats = (
                Reader.objects
                .filter(change_date__gte=first_day_of_month)
                .order_by('number')
                .values('number')
                .annotate(
                    balloons_month=Count('pk'),
                    rfid_month=Count('pk', filter=Q(nfc_tag__isnull=False))
                )
            )

            # Баллонов за текущий день
            balloons_today_stats = (
                Reader.objects
                .filter(change_date=today)
                .values('number')
                .annotate(
                    balloons_month=Count('pk'),
                    rfid_month=Count('pk', filter=Q(nfc_tag__isnull=False))
                )
            )

            # Партий за текущий месяц
            loading_batches_last_month = (BalloonsLoadingBatch.objects
                                          .filter(begin_date__gte=first_day_of_month)
                                          .values('reader_number')
                                          .annotate(month_batches=Count('id'))
                                          )
            unloading_batches_last_month = (BalloonsUnloadingBatch.objects
                                            .filter(begin_date__gte=first_day_of_month)
                                            .values('reader_number')
                                            .annotate(month_batches=Count('id'))
                                            )
            # Объединяем результаты по партиям за последний месяц
            batches_last_month = {}
            for batch in loading_batches_last_month:
                reader_number = batch['reader_number']
                batches_last_month[reader_number] = batches_last_month.get(reader_number, 0) + batch['month_batches']

            for batch in unloading_batches_last_month:
                reader_number = batch['reader_number']
                batches_last_month[reader_number] = batches_last_month.get(reader_number, 0) + batch['month_batches']

            # Партий за текущий день
            loading_batches_last_day = (BalloonsLoadingBatch.objects
                                        .filter(begin_date=today)
                                        .values('reader_number')
                                        .annotate(day_batches=Count('id'))
                                        )
            unloading_batches_last_day = (BalloonsUnloadingBatch.objects
                                          .filter(begin_date=today)
                                          .values('reader_number')
                                          .annotate(day_batches=Count('id'))
                                          )
            # Объединяем результаты по партиям за последний день
            batches_last_day = {}
            for batch in loading_batches_last_day:
                reader_number = batch['reader_number']
                batches_last_day[reader_number] = batches_last_day.get(reader_number, 0) + batch['day_batches']

            for batch in unloading_batches_last_day:
                reader_number = batch['reader_number']
                batches_last_day[reader_number] = batches_last_day.get(reader_number, 0) + batch['day_batches']

            # Преобразуем данные по баллонам за сегодня в словарь для быстрого доступа
            today_dict = {stat['reader_id']: stat for stat in balloons_today_stats}

            # Объединяем данные
            response = []
            for stat in balloons_monthly_stats:
                reader_id = stat['reader_id']
                balloons_today = today_dict.get(reader_id, {}).get('balloons_today', 0)
                rfid_today = today_dict.get(reader_id, {}).get('rfid_today', 0)
                truck_month = batches_last_month.get(reader_id, 0)
                truck_today = batches_last_day.get(reader_id, 0)

                # Создаем новый словарь с данными
                response.append({
                    'reader_id': reader_id,
                    'balloons_month': stat['balloons_month'],
                    'rfid_month': stat['rfid_month'],
                    'balloons_today': balloons_today,
                    'rfid_today': rfid_today,
                    'truck_month': truck_month,
                    'truck_today': truck_today
                })

            response.append({
                'filled_balloons_on_station': filled_balloons_on_station.get('total', 0),
                'empty_balloons_on_station': empty_balloons_on_station.get('total', 0)
            })
            data = response
        cache.set(cache_key, data, cache_time)
        return JsonResponse(data, safe=False)

    def create(self, request):
        nfc_tag = request.data.get('nfc_tag', None)
        balloons = Balloon.objects.filter(nfc_tag=nfc_tag).exists()
        if not balloons:
            serializer = BalloonSerializer(data=request.data)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        return Response(status=status.HTTP_409_CONFLICT)

    def partial_update(self, request, pk=None):
        balloon = get_object_or_404(Balloon, id=pk)

        serializer = BalloonSerializer(balloon, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@receiver(post_save, sender=Balloon)
@receiver(post_save, sender=Reader)
@receiver(post_save, sender=BalloonsLoadingBatch)
@receiver(post_save, sender=BalloonsUnloadingBatch)
@receiver(post_delete, sender=Balloon)
@receiver(post_delete, sender=Reader)
@receiver(post_delete, sender=BalloonsLoadingBatch)
@receiver(post_delete, sender=BalloonsUnloadingBatch)
def clear_cache(sender, **kwargs):
    cache.delete('get_balloon_statistic')


@api_view(['GET'])
def get_balloon_status_options(request):
    return Response(USER_STATUS_LIST)


@api_view(['GET'])
def get_loading_balloon_reader_list(request):
    return Response(BALLOONS_LOADING_READER_LIST)


@api_view(['GET'])
def get_unloading_balloon_reader_list(request):
    return Response(BALLOONS_UNLOADING_READER_LIST)

# Схемы для Swagger
BalloonOperationResponse = inline_serializer(
    name='BalloonOperationResponse',
    fields={
        'success': serializers.BooleanField(),
        'balloon_id': serializers.IntegerField(allow_null=True),
        'new_count': serializers.IntegerField(),
        'error': serializers.CharField()
    }
)

@extend_schema_view(
    is_active=extend_schema(
        tags=['Партии приёмки баллонов'],
        summary='Получить активные партии',
        description='Получение списка всех активных партий приёмки баллонов',
        responses={
            200: ActiveLoadingBatchSerializer(many=True),
            404: OpenApiTypes.OBJECT
        },
        examples=[
            OpenApiExample(
                'Пример ответа',
                value=[{
                    "id": 1,
                    "begin_date": "2023-05-15",
                    "begin_time": "08:30:00",
                    "truck": 1,
                    "trailer": 1,
                    "amount_of_rfid": 15,
                    "is_active": True
                }],
                response_only=True
            )
        ]
    ),
    last_active=extend_schema(
        tags=['Партии приёмки баллонов'],
        summary='Получить последнюю активную партию',
        description='Получение данных последней созданной активной партии приёмки',
        responses={
            200: BalloonsLoadingBatchSerializer,
            404: OpenApiTypes.OBJECT
        }
    ),
    rfid_amount=extend_schema(
        tags=['Партии приёмки баллонов'],
        summary='Количество баллонов по RFID',
        description='Получение количества баллонов в партии, зарегистрированных по RFID',
        parameters=[
            OpenApiParameter(
                name='id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='ID партии приёмки'
            )
        ],
        responses={
            200: BalloonAmountLoadingSerializer,
            404: OpenApiTypes.OBJECT
        }
    ),
    create=extend_schema(
        tags=['Партии приёмки баллонов'],
        summary='Создать новую партию',
        description='Создание новой партии приёмки баллонов',
        request=BalloonsLoadingBatchSerializer,
        responses={
            201: BalloonsLoadingBatchSerializer,
            400: OpenApiTypes.OBJECT
        },
        examples=[
            OpenApiExample(
                'Пример запроса',
                value={
                    "truck": 1,
                    "trailer": 1,
                    "reader_number": 2,
                    "ttn": "AB123456",
                    "amount_of_ttn": 50,
                    "is_active": True
                },
                request_only=True
            )
        ]
    ),
    partial_update=extend_schema(
        tags=['Партии приёмки баллонов'],
        summary='Обновить партию',
        description='Частичное обновление данных партии приёмки',
        request=BalloonsLoadingBatchSerializer,
        responses={
            200: BalloonsLoadingBatchSerializer,
            400: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT
        },
        examples=[
            OpenApiExample(
                'Пример запроса на завершение партии',
                value={
                    "is_active": False,
                    "amount_of_5_liters": 10,
                    "amount_of_12_liters": 15,
                    "amount_of_27_liters": 20,
                    "amount_of_50_liters": 5,
                    "gas_amount": 1500.5
                },
                request_only=True
            )
        ]
    ),
    add_balloon=extend_schema(
        tags=['Партии приёмки баллонов'],
        summary='Добавить баллон в партию',
        description='Добавление баллона в партию приёмки по NFC метке',
        request=inline_serializer(
            name='AddBalloonRequest',
            fields={
                'nfc': serializers.CharField()
            }
        ),
        parameters=[
            OpenApiParameter(
                name='id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='ID партии приёмки'
            )
        ],
        responses={
            200: BalloonOperationResponse,
            400: BalloonOperationResponse,
            404: BalloonOperationResponse,
            409: BalloonOperationResponse
        },
        examples=[
            OpenApiExample(
                'Успешное добавление',
                value={
                    'success': True,
                    'balloon_id': 123,
                    'new_count': 15,
                    'error': 'ok'
                },
                response_only=True,
                status_codes=['200']
            ),
            OpenApiExample(
                'Баллон уже в партии',
                value={
                    'success': False,
                    'balloon_id': 123,
                    'new_count': 14,
                    'error': 'Баллон уже в партии'
                },
                response_only=True,
                status_codes=['409']
            ),
            OpenApiExample(
                'Баллон не найден',
                value={
                    'success': False,
                    'balloon_id': None,
                    'new_count': 14,
                    'error': 'Баллон не найден'
                },
                response_only=True,
                status_codes=['404']
            )
        ]
    ),
    remove_balloon=extend_schema(
        tags=['Партии приёмки баллонов'],
        summary='Удалить баллон из партии',
        description='Удаление баллона из партии приёмки по NFC метке',
        request=inline_serializer(
            name='RemoveBalloonRequest',
            fields={
                'nfc': serializers.CharField()
            }
        ),
        parameters=[
            OpenApiParameter(
                name='id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='ID партии приёмки'
            )
        ],
        responses={
            200: BalloonOperationResponse,
            400: BalloonOperationResponse,
            404: BalloonOperationResponse
        },
        examples=[
            OpenApiExample(
                'Успешное удаление',
                value={
                    'success': True,
                    'balloon_id': 123,
                    'new_count': 14,
                    'error': 'ok'
                },
                response_only=True,
                status_codes=['200']
            ),
            OpenApiExample(
                'Баллон не найден в партии',
                value={
                    'success': False,
                    'balloon_id': 123,
                    'new_count': 15,
                    'error': 'Баллон не найден в партии'
                },
                response_only=True,
                status_codes=['404']
            )
        ]
    )
)
class BalloonsLoadingBatchViewSet(viewsets.ViewSet):
    """
    API для управления партиями приёмки баллонов

    Позволяет:
    - Создавать и обновлять партии приёмки
    - Управлять активными партиями
    - Добавлять/удалять баллоны по NFC
    - Получать статистику по партиям
    """
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'], url_path='active')
    def is_active(self, request):
        batches = BalloonsLoadingBatch.objects.filter(is_active=True)
        serializer = ActiveLoadingBatchSerializer(batches, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='last-active')
    def last_active(self, request):
        batch = BalloonsLoadingBatch.objects.filter(is_active=True).first()
        if not batch:
            return Response(status=status.HTTP_404_NOT_FOUND)
        serializer = BalloonsLoadingBatchSerializer(batch)
        return Response(serializer.data)

    @action(detail=True, methods=['get'], url_path='rfid-amount')
    def rfid_amount(self, request, pk=None):
        batch = get_object_or_404(BalloonsLoadingBatch, id=pk)
        serializer = BalloonAmountLoadingSerializer(batch)
        return Response(serializer.data)

    def create(self, request):
        serializer = BalloonsLoadingBatchSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def partial_update(self, request, pk=None):
        batch = get_object_or_404(BalloonsLoadingBatch, id=pk)

        if not request.data.get('is_active', True):
            current_date = datetime.now()
            request.data['end_date'] = current_date.date()
            request.data['end_time'] = current_date.time()

        serializer = BalloonsLoadingBatchSerializer(batch, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['patch'], url_path='add-balloon')
    def add_balloon(self, request, pk=None):
        nfc = request.data.get('nfc')
        if not nfc:
            return Response(
                {"error": "Параметр 'nfc' обязателен"},
                status=status.HTTP_400_BAD_REQUEST
            )

        batch = get_object_or_404(BalloonsLoadingBatch, id=pk)
        result = batch.add_balloon(nfc)

        if result['success']:
            return Response(result, status=status.HTTP_200_OK)

        error_status = {
            'Баллон уже в партии': status.HTTP_409_CONFLICT,
            'Баллон не найден': status.HTTP_404_NOT_FOUND
        }.get(result['error'], status.HTTP_400_BAD_REQUEST)

        return Response(result, status=error_status)

    @action(detail=True, methods=['patch'], url_path='remove-balloon')
    def remove_balloon(self, request, pk=None):
        nfc = request.data.get('nfc')
        if not nfc:
            return Response(
                {"error": "Параметр 'nfc' обязателен"},
                status=status.HTTP_400_BAD_REQUEST
            )

        batch = get_object_or_404(BalloonsLoadingBatch, id=pk)
        result = batch.remove_balloon(nfc)

        if result['success']:
            return Response(result, status=status.HTTP_200_OK)

        error_status = {
            'Баллон не найден в партии': status.HTTP_404_NOT_FOUND,
            'Баллон не найден': status.HTTP_404_NOT_FOUND
        }.get(result['error'], status.HTTP_400_BAD_REQUEST)

        return Response(result, status=error_status)


@extend_schema_view(
    is_active=extend_schema(
        tags=['Партии отгрузки баллонов'],
        summary='Активные партии отгрузки',
        description='Получение списка активных партий отгрузки баллонов',
        responses={
            200: ActiveUnloadingBatchSerializer(many=True),
            404: OpenApiTypes.OBJECT
        },
        examples=[
            OpenApiExample(
                'Пример ответа',
                value=[{
                    "id": 1,
                    "begin_date": "2023-05-15",
                    "begin_time": "09:30:00",
                    "truck": {"id": 1, "registration_number": "А123БВ777"},
                    "trailer": {"id": 1, "registration_number": "ПТ987ХВ"},
                    "amount_of_rfid": 12,
                    "is_active": True,
                    "ttn": "ТТН-789012"
                }],
                response_only=True
            )
        ]
    ),
    last_active=extend_schema(
        tags=['Партии отгрузки баллонов'],
        summary='Последняя активная партия',
        description='Получение данных последней активной партии отгрузки',
        responses={
            200: BalloonsUnloadingBatchSerializer,
            404: OpenApiTypes.OBJECT
        }
    ),
    rfid_amount=extend_schema(
        tags=['Партии отгрузки баллонов'],
        summary='Количество RFID-баллонов',
        description='Получение количества баллонов в партии, зарегистрированных по RFID',
        parameters=[
            OpenApiParameter(
                name='id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='ID партии отгрузки'
            )
        ],
        responses={
            200: BalloonAmountUnloadingSerializer,
            404: OpenApiTypes.OBJECT
        }
    ),
    create=extend_schema(
        tags=['Партии отгрузки баллонов'],
        summary='Создать партию отгрузки',
        description='Создание новой партии отгрузки баллонов',
        request=BalloonsUnloadingBatchSerializer,
        responses={
            201: BalloonsUnloadingBatchSerializer,
            400: OpenApiTypes.OBJECT
        },
        examples=[
            OpenApiExample(
                'Пример запроса',
                value={
                    "truck": 1,
                    "trailer": 1,
                    "reader_number": 3,
                    "ttn": "ТТН-789012",
                    "amount_of_ttn": 25,
                    "is_active": True
                },
                request_only=True
            )
        ]
    ),
    partial_update=extend_schema(
        tags=['Партии отгрузки баллонов'],
        summary='Обновить партию отгрузки',
        description='Обновление данных партии отгрузки баллонов',
        request=BalloonsUnloadingBatchSerializer,
        responses={
            200: BalloonsUnloadingBatchSerializer,
            400: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT
        },
        examples=[
            OpenApiExample(
                'Пример запроса',
                value={
                    "is_active": False,
                    "amount_of_5_liters": 8,
                    "amount_of_12_liters": 10,
                    "amount_of_27_liters": 5,
                    "amount_of_50_liters": 2,
                    "gas_amount": 1200.75,
                    "end_date": "2023-05-15",
                    "end_time": "17:45:00"
                },
                request_only=True
            )
        ]
    ),
    add_balloon=extend_schema(
        tags=['Партии отгрузки баллонов'],
        summary='Добавить баллон в отгрузку',
        description='Добавление баллона в партию отгрузки по NFC метке',
        request=inline_serializer(
            name='AddBalloonToUnloadingRequest',
            fields={
                'nfc': serializers.CharField()
            }
        ),
        parameters=[
            OpenApiParameter(
                name='id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='ID партии отгрузки'
            )
        ],
        responses={
            200: BalloonOperationResponse,
            400: BalloonOperationResponse,
            404: BalloonOperationResponse,
            409: BalloonOperationResponse
        },
        examples=[
            OpenApiExample(
                'Успешное добавление',
                value={
                    'success': True,
                    'balloon_id': 45,
                    'new_count': 13,
                    'error': 'ok'
                },
                response_only=True,
                status_codes=['200']
            ),
            OpenApiExample(
                'Ошибка: баллон уже в партии',
                value={
                    'success': False,
                    'balloon_id': 45,
                    'new_count': 12,
                    'error': 'Баллон уже в партии'
                },
                response_only=True,
                status_codes=['409']
            )
        ]
    ),
    remove_balloon=extend_schema(
        tags=['Партии отгрузки баллонов'],
        summary='Удалить баллон из отгрузки',
        description='Удаление баллона из партии отгрузки по NFC метке',
        request=inline_serializer(
            name='RemoveBalloonFromUnloadingRequest',
            fields={
                'nfc': serializers.CharField()
            }
        ),
        parameters=[
            OpenApiParameter(
                name='id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='ID партии отгрузки'
            )
        ],
        responses={
            200: BalloonOperationResponse,
            400: BalloonOperationResponse,
            404: BalloonOperationResponse
        },
        examples=[
            OpenApiExample(
                'Успешное удаление',
                value={
                    'success': True,
                    'balloon_id': 45,
                    'new_count': 11,
                    'error': 'ok'
                },
                response_only=True,
                status_codes=['200']
            ),
            OpenApiExample(
                'Ошибка: баллон не найден',
                value={
                    'success': False,
                    'balloon_id': None,
                    'new_count': 12,
                    'error': 'Баллон не найден в партии'
                },
                response_only=True,
                status_codes=['404']
            )
        ]
    )
)
class BalloonsUnloadingBatchViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'], url_path='active')
    def is_active(self, request):
        batches = BalloonsUnloadingBatch.objects.filter(is_active=True)
        serializer = ActiveUnloadingBatchSerializer(batches, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='last-active')
    def last_active(self, request):
        batch = BalloonsUnloadingBatch.objects.filter(is_active=True).first()
        if not batch:
            return Response(status=status.HTTP_404_NOT_FOUND)
        serializer = BalloonsUnloadingBatchSerializer(batch)
        return Response(serializer.data)

    @action(detail=True, methods=['get'], url_path='rfid-amount')
    def rfid_amount(self, request, pk=None):
        batch = get_object_or_404(BalloonsUnloadingBatch, id=pk)
        serializer = BalloonAmountUnloadingSerializer(batch)
        return Response(serializer.data)

    def create(self, request):
        serializer = BalloonsUnloadingBatchSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def partial_update(self, request, pk=None):
        batch = get_object_or_404(BalloonsUnloadingBatch, id=pk)

        if not request.data.get('is_active', True):
            current_date = datetime.now()
            request.data['end_date'] = current_date.date()
            request.data['end_time'] = current_date.time()

        serializer = BalloonsUnloadingBatchSerializer(batch, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['patch'], url_path='add-balloon')
    def add_balloon(self, request, pk=None):
        nfc = request.data.get('nfc')
        if not nfc:
            return Response(
                {"error": "Параметр 'nfc' обязателен"},
                status=status.HTTP_400_BAD_REQUEST
            )

        batch = get_object_or_404(BalloonsUnloadingBatch, id=pk)
        result = batch.add_balloon(nfc)

        if result['success']:
            return Response(result, status=status.HTTP_200_OK)

        error_status = {
            'Баллон уже в партии': status.HTTP_409_CONFLICT,
            'Баллон не найден': status.HTTP_404_NOT_FOUND
        }.get(result['error'], status.HTTP_400_BAD_REQUEST)

        return Response(result, status=error_status)

    @action(detail=True, methods=['patch'], url_path='remove-balloon')
    def remove_balloon(self, request, pk=None):
        nfc = request.data.get('nfc')
        if not nfc:
            return Response(
                {"error": "Параметр 'nfc' обязателен"},
                status=status.HTTP_400_BAD_REQUEST
            )

        batch = get_object_or_404(BalloonsUnloadingBatch, id=pk)
        result = batch.remove_balloon(nfc)

        if result['success']:
            return Response(result, status=status.HTTP_200_OK)

        error_status = {
            'Баллон не найден в партии': status.HTTP_404_NOT_FOUND,
            'Баллон не найден': status.HTTP_404_NOT_FOUND
        }.get(result['error'], status.HTTP_400_BAD_REQUEST)

        return Response(result, status=error_status)


@api_view(['GET'])
def get_active_balloon_batch(request):
    """
    Метод получения списков активных партий
    """
    today = date.today()
    loading_batches = BalloonsLoadingBatch.objects.filter(begin_date=today, is_active=True)
    unloading_batches = BalloonsUnloadingBatch.objects.filter(begin_date=today, is_active=True)

    response = []
    for batch in loading_batches:
        response.append({
            'reader_id': batch.reader_number,
            'truck_registration_number': batch.truck.registration_number,
            'trailer_registration_number': batch.trailer.registration_number
        })
    for batch in unloading_batches:
        response.append({
            'reader_id': batch.reader_number,
            'truck_registration_number': batch.truck.registration_number,
            'trailer_registration_number': batch.trailer.registration_number
        })
    return JsonResponse(response, safe=False)
