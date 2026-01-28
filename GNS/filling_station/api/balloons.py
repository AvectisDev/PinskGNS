import logging
from collections import defaultdict
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Q, Sum, Count
from django.shortcuts import get_object_or_404
from django.core.cache import cache
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from rest_framework import generics, status, viewsets, serializers
from rest_framework.response import Response
from rest_framework.decorators import api_view, action, permission_classes
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
from filling_station.models import Balloon, Reader, BalloonsBatch, DailyReaderCounter, TotalReadersCounter
from .serializers import (
    BalloonSerializer,
    BalloonsBatchSerializer,
    ActiveBatchSerializer,
    BalloonAmountSerializer
)
from .. import services
from ttn.services import close_ttn_in_miriada


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


# Схемы для Swagger
ErrorResponseSerializer = inline_serializer(
    name='ErrorResponse',
    fields={
        'error': serializers.CharField()
    }
)

UpdateByReaderResponseSerializer = inline_serializer(
    name='UpdateByReaderResponse',
    fields={
        'status': serializers.CharField(),
        'balloon': BalloonSerializer()
    }
)

@extend_schema_view(
    get_by_nfc=extend_schema(
        tags=['Баллоны'],
        summary='Получить баллон по NFC метке',
        description='Получение информации о баллоне по его NFC метке',
        parameters=[
            OpenApiParameter(
                name='nfc_tag',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.PATH,
                description='NFC метка баллона',
                examples=[
                    OpenApiExample(
                        'Пример NFC метки',
                        value='1234567890ABCDEF'
                    )
                ]
            )
        ],
        responses={
            200: BalloonSerializer,
            404: ErrorResponseSerializer
        },
        examples=[
            OpenApiExample(
                'Пример успешного ответа',
                value={
                    "nfc_tag": "1234567890ABCDEF",
                    "serial_number": "B12345",
                    "size": 50,
                    "netto": 18.5,
                    "brutto": 40.2,
                    "status": "На складе",
                    "filling_status": True
                },
                response_only=True
            )
        ]
    ),
    get_by_serial_number=extend_schema(
        tags=['Баллоны'],
        summary='Получить баллоны по серийному номеру',
        description='Поиск всех баллонов с указанным серийным номером',
        parameters=[
            OpenApiParameter(
                name='serial_number',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.PATH,
                description='Серийный номер баллона',
                examples=[
                    OpenApiExample(
                        'Пример серийного номера',
                        value='B12345'
                    )
                ]
            )
        ],
        responses={
            200: BalloonSerializer(many=True),
            404: ErrorResponseSerializer
        },
        examples=[
            OpenApiExample(
                'Пример ответа с несколькими баллонами',
                value=[{
                    "nfc_tag": "1234567890ABCDEF",
                    "serial_number": "B12345",
                    "size": 50,
                    "netto": 18.5,
                    "brutto": 40.2,
                    "status": "На складе",
                    "filling_status": True
                }],
                response_only=True
            )
        ]
    ),
    create = extend_schema(
        tags=['Баллоны'],
        summary='Создать новый баллон',
        description='Создание нового баллона с проверкой уникальности NFC метки',
        request=BalloonSerializer,
        responses={
            201: BalloonSerializer,
            400: inline_serializer(
                name='BalloonCreateError',
                fields={
                    'errors': serializers.DictField()
                }
            ),
            409: OpenApiTypes.OBJECT
        },
        examples=[
            OpenApiExample(
                'Пример запроса',
                value={
                    "nfc_tag": "1234567890ABCDEF",
                    "serial_number": "B12345",
                    "size": 50,
                    "netto": 18.5,
                    "brutto": 40.2,
                    "status": "На складе"
                },
                request_only=True
            ),
            OpenApiExample(
                'Успешный ответ',
                value={
                    "nfc_tag": "1234567890ABCDEF",
                    "serial_number": "B12345",
                    "size": 50,
                    "netto": 18.5,
                    "brutto": 40.2,
                    "status": "На складе",
                    "filling_status": True
                },
                response_only=True,
                status_codes=['201']
            ),
            OpenApiExample(
                'Ошибка валидации',
                value={
                    "errors": {
                        "size": ["Обязательное поле."],
                        "netto": ["Введите число."]
                    }
                },
                response_only=True,
                status_codes=['400']
            ),
            OpenApiExample(
                'Конфликт NFC метки',
                value={
                    "detail": "Баллон с такой NFC меткой уже существует"
                },
                response_only=True,
                status_codes=['409']
            )
        ]
    ),
    get_statistic=extend_schema(
        tags=['Баллоны'],
        summary='Получение статистики по ГНС',
        description='Получение статистики по ГНС',
    ),
    partial_update=extend_schema(
        tags=['Баллоны'],
        summary='Частичное обновление баллона',
        description='Обновление отдельных полей баллона по его NFC метке',
        request=BalloonSerializer,
        parameters=[
            OpenApiParameter(
                name='id',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.PATH,
                description='NFC метка баллона (первичный ключ)',
                required=True,
                examples=[
                    OpenApiExample(
                        'Пример NFC метки',
                        value='1234567890ABCDEF'
                    )
                ]
            )
        ],
        responses={
            200: BalloonSerializer,
            400: inline_serializer(
                name='BalloonUpdateError',
                fields={
                    'errors': serializers.DictField()
                }
            ),
            404: OpenApiTypes.OBJECT
        },
        examples=[
            OpenApiExample(
                'Пример запроса на обновление',
                value={
                    "status": "В ремонте",
                    "filling_status": False,
                    "wall_thickness": 5.2
                },
                request_only=True
            ),
            OpenApiExample(
                'Успешный ответ',
                value={
                    "nfc_tag": "1234567890ABCDEF",
                    "serial_number": "B12345",
                    "status": "В ремонте",
                    "filling_status": False,
                    "wall_thickness": 5.2,
                },
                response_only=True,
                status_codes=['200']
            )
        ]
    )
)
class BalloonViewSet(viewsets.ViewSet):
    """
    ViewSet для работы с газовыми баллонами.
    Позволяет получать информацию о баллонах по различным критериям
    и обновлять данные при срабатывании RFID считывателей.
    """
    permission_classes = [IsAuthenticated]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger = logging.getLogger(__name__)

    @action(detail=False, methods=['get'], url_path='nfc/(?P<nfc_tag>[^/.]+)')
    def get_by_nfc(self, request, nfc_tag=None):
        """
        Получение информации о баллоне по его NFC метке.
        Args:
            request: HTTP запрос
            nfc_tag (str): Уникальный идентификатор NFC метки
        Returns:
            Response: Сериализованные данные баллона или 404 если не найден
        Raises:
            Http404: Если баллон с указанной меткой не существует
        """
        balloon = Balloon.objects.select_related('user').filter(nfc_tag=nfc_tag).first()
        if not balloon:
            return Response(
                {"message": f"Баллон с NFC-тегом {nfc_tag} не найден"},
                status=status.HTTP_404_NOT_FOUND
            )
        serializer = BalloonSerializer(balloon)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='serial-number/(?P<serial_number>[^/.]+)')
    def get_by_serial_number(self, request, serial_number=None):
        """
        Получение информации о баллоне по его серийному номеру.
        Args:
            request: HTTP запрос
            serial_number (str): Серийный номер баллона
        Returns:
            Response: Список баллонов с указанным серийным номером
                     (может быть пустым)
        """
        balloons = Balloon.objects.select_related('user').filter(serial_number=serial_number)
        if not balloons:
            return Response(
                {"message": f"Баллон с серийным номером {serial_number} не найден"},
                status=status.HTTP_404_NOT_FOUND
            )
        serializer = BalloonSerializer(balloons, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='statistic')
    def get_statistic(self, request):
        """
        Получение сводной статистики по баллонам и операциям на ГНС.
        Возвращает кэшированные (на 10 минут) данные в формате:
        [
            {
                "reader_id": int, # Номер считывателя (1-8)
                "balloons_month": int, # Всего баллонов за месяц
                "rfid_month": int, # Баллонов с RFID за месяц
                "balloons_today": int, # Всего баллонов за сегодня
                "rfid_today": int, # Баллонов с RFID за сегодня
                "truck_month": int, # Партий (грузовиков) за месяц
                "truck_today": int # Партий (грузовиков) за сегодня},
            ...,
            {"filled_balloons_on_station": int, # Заполненных баллонов на станции
                "empty_balloons_on_station": int # Пустых баллонов на станции}
        ]
        Логика работы:
        1. Проверяет наличие данных в кэше
        2. Если данных нет в кэше:
           - Получает базовую статистику по считывателям
           - Получает статистику по партиям погрузки/выгрузки
           - Получает данные о баллонах на станции
           - Объединяет все данные в единую структуру
        3. Сохраняет результат в кэш на 10 минут

        Returns:
            JsonResponse:
                - 200 OK с данными статистики
        """
        cache_key = 'get_balloon_statistic'
        cache_time = 600  # 10 минут
        data = cache.get(cache_key)

        if not data:
            reader_stats = DailyReaderCounter.get_common_stats_for_gns()
            loading_batches = BalloonsBatch.get_common_stats_for_gns(batch_type='l')
            unloading_batches = BalloonsBatch.get_common_stats_for_gns(batch_type='u')
            balloons_stat = TotalReadersCounter.get_balloons_stats()

            # Словарь для хранения суммарной статистики по грузовикам
            truck_stats = defaultdict(lambda: {"truck_month": 0, "truck_today": 0})

            # Суммируем данные из погрузки
            for item in loading_batches:
                reader_id = item["reader_id"]
                truck_stats[reader_id]["truck_month"] += item.get("truck_month", 0)
                truck_stats[reader_id]["truck_today"] += item.get("truck_today", 0)

            # Суммируем данные из разгрузки
            for item in unloading_batches:
                reader_id = item["reader_id"]
                truck_stats[reader_id]["truck_month"] += item.get("truck_month", 0)
                truck_stats[reader_id]["truck_today"] += item.get("truck_today", 0)

            # Объединяем с основной статистикой
            response = []
            for item in reader_stats:
                reader_id = item["reader_id"]
                merged_entry = item.copy()
                merged_entry["truck_month"] = truck_stats[reader_id]["truck_month"]
                merged_entry["truck_today"] = truck_stats[reader_id]["truck_today"]
                response.append(merged_entry)

            response.append({
                'filled_balloons_on_station': balloons_stat['filled'],
                'empty_balloons_on_station': balloons_stat['empty']
            })
            data = response
        cache.set(cache_key, data, cache_time)
        return JsonResponse(data, safe=False)

    def create(self, request):
        """
        Создает новый баллон после проверки уникальности NFC метки.
        Args:
            request: Запрос с данными нового баллона
                - nfc_tag (str): Уникальный идентификатор NFC метки (обязательный)
                - другие поля согласно BalloonSerializer
        Returns:
            Response:
                - 201 Created с данными баллона при успехе
                - 400 Bad Request с ошибками валидации
                - 409 Conflict если баллон с такой NFC меткой уже существует
        """
        nfc_tag = request.data.get('nfc_tag', None)
        balloons = Balloon.objects.filter(nfc_tag=nfc_tag).exists()
        if not balloons:
            serializer = BalloonSerializer(data=request.data)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {'message': f'Баллон с такой NFC меткой уже существует'},
            status=status.HTTP_409_CONFLICT)

    def partial_update(self, request, pk=None):
        """
        Частично обновляет данные баллона.
        Args:
            request: Запрос с данными для обновления
            pk (str): NFC метка баллона (первичный ключ)
        Returns:
            Response:
                - 200 OK с обновленными данными баллона
                - 400 Bad Request с ошибками валидации
                - 404 Not Found если баллон не существует
        """
        balloon = Balloon.objects.select_related('user').filter(nfc_tag=pk).first()
        if not balloon:
            return Response(
                {"message": f"Баллон с NFC-тегом {pk} не найден"},
                status=status.HTTP_404_NOT_FOUND
            )

        new_tag = request.data.get('nfc_tag', None)

        if pk != new_tag:  # Процедура смены метки
            if Balloon.objects.filter(nfc_tag=new_tag).exists():
                return Response(
                    {"message": f"Баллон с NFC-тегом {new_tag} уже существует"},
                    status=status.HTTP_400_BAD_REQUEST
                    )
            else:
                balloon.delete()
                serializer = BalloonSerializer(data=request.data, partial=True)
                if serializer.is_valid():
                    serializer.save()
                    return Response(serializer.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        serializer = BalloonSerializer(balloon, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@receiver(post_save, sender=Balloon)
@receiver(post_save, sender=Reader)
@receiver(post_save, sender=BalloonsBatch)
@receiver(post_delete, sender=Balloon)
@receiver(post_delete, sender=Reader)
@receiver(post_delete, sender=BalloonsBatch)
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

# --- TotalReadersCounter (ручной ввод) ---
ManualTotalReadersCounterRequestSerializer = inline_serializer(
    name='ManualTotalReadersCounterRequest',
    fields={
        'empty': serializers.IntegerField(
            required=False,
            min_value=0,
            help_text='Ручное значение для количества пустых баллонов (total_empty)'
        ),
        'full': serializers.IntegerField(
            required=False,
            min_value=0,
            help_text='Ручное значение для количества полных баллонов (total_full)'
        ),
    }
)

ManualTotalReadersCounterResponseSerializer = inline_serializer(
    name='ManualTotalReadersCounterResponse',
    fields={
        'total_empty': serializers.IntegerField(),
        'total_full': serializers.IntegerField(),
        'changed_at': serializers.DateTimeField(),
    }
)


@extend_schema(
    tags=['Свод по складу'],
    summary='Ручной ввод итоговых счетчиков (пустые/полные)',
    description=(
        'Записывает переданные значения в таблицу `TotalReadersCounter` (singleton `pk=1`). '
        'Можно передать только `empty`, только `full` или оба поля.'
    ),
    request=ManualTotalReadersCounterRequestSerializer,
    responses={
        200: ManualTotalReadersCounterResponseSerializer,
        400: ErrorResponseSerializer,
    },
    examples=[
        OpenApiExample(
            'Пример запроса (оба поля)',
            value={'empty': 25, 'full': 7},
            request_only=True
        ),
        OpenApiExample(
            'Пример запроса (только empty)',
            value={'empty': 10},
            request_only=True
        ),
        OpenApiExample(
            'Пример успешного ответа',
            value={'total_empty': 25, 'total_full': 7, 'changed_at': '2026-01-28T10:15:30Z'},
            response_only=True
        ),
    ]
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def set_total_readers_counter_manual_values(request):
    """
    Запись ручных значений `TotalReadersCounter` через API.
    """
    empty = request.data.get('empty', None)
    full = request.data.get('full', None)

    # Валидируем через DRF поля (включая min_value)
    req_serializer = ManualTotalReadersCounterRequestSerializer(data={'empty': empty, 'full': full})
    if not req_serializer.is_valid():
        return Response({'error': req_serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    validated = req_serializer.validated_data
    if 'empty' not in validated and 'full' not in validated:
        return Response({'error': 'Нужно передать хотя бы одно поле: empty или full'}, status=status.HTTP_400_BAD_REQUEST)

    # гарантируем, что singleton существует
    TotalReadersCounter.objects.get_or_create(pk=1, defaults={'total_empty': 0, 'total_full': 0})
    TotalReadersCounter.insert_manual_values(
        empty=validated.get('empty', None),
        full=validated.get('full', None)
    )
    obj = TotalReadersCounter.objects.get(pk=1)
    return Response(
        {
            'total_empty': obj.total_empty,
            'total_full': obj.total_full,
            'changed_at': obj.changed_at,
        },
        status=status.HTTP_200_OK
    )

# Схемы для Swagger
BalloonOperationResponse = inline_serializer(
    name='BalloonOperationResponse',
    fields={
        'success': serializers.BooleanField(),
        'balloon_id': serializers.CharField(allow_null=True),
        'new_count': serializers.IntegerField(),
        'error': serializers.CharField()
    }
)

@extend_schema_view(
    is_active=extend_schema(
        tags=['Партии баллонов'],
        summary='Получить активные партии',
        description='Получение списка всех активных партий баллонов по типу',
        parameters=[
            OpenApiParameter(
                name='batch_type',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Тип партии: l (приёмка) или u (отгрузка)',
                enum=['l', 'u']
            )
        ],
        responses={
            200: ActiveBatchSerializer(many=True),
            404: OpenApiTypes.OBJECT
        }
    ),
    last_active=extend_schema(
        tags=['Партии баллонов'],
        summary='Получить последнюю активную партию',
        description='Получение данных последней созданной активной партии по типу',
        parameters=[
            OpenApiParameter(
                name='batch_type',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Тип партии: l (приёмка) или u (отгрузка)',
                enum=['l', 'u']
            )
        ],
        responses={
            200: BalloonsBatchSerializer,
            404: OpenApiTypes.OBJECT
        }
    ),
    rfid_amount=extend_schema(
        tags=['Партии баллонов'],
        summary='Количество баллонов по RFID',
        description='Получение количества баллонов в партии, зарегистрированных по RFID',
        parameters=[
            OpenApiParameter(
                name='id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='ID партии'
            )
        ],
        responses={
            200: BalloonAmountSerializer,
            404: OpenApiTypes.OBJECT
        }
    ),
    create=extend_schema(
        tags=['Партии баллонов'],
        summary='Создать новую партию',
        description='Создание новой партии баллонов с привязкой к ТТН',
        request=BalloonsBatchSerializer,
        responses={
            201: BalloonsBatchSerializer,
            400: OpenApiTypes.OBJECT
        }
    ),
    partial_update=extend_schema(
        tags=['Партии баллонов'],
        summary='Обновить партию',
        description='Частичное обновление данных партии',
        request=BalloonsBatchSerializer,
        responses={
            200: BalloonsBatchSerializer,
            400: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT
        }
    ),
    add_balloon=extend_schema(
        tags=['Партии баллонов'],
        summary='Добавить баллон в партию',
        description='Добавление баллона в партию по NFC метке',
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
                description='ID партии'
            )
        ],
        responses={
            200: BalloonOperationResponse,
            400: BalloonOperationResponse,
            404: BalloonOperationResponse,
            409: BalloonOperationResponse
        }
    ),
    remove_balloon=extend_schema(
        tags=['Партии баллонов'],
        summary='Удалить баллон из партии',
        description='Удаление баллона из партии по NFC метке',
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
                description='ID партии'
            )
        ],
        responses={
            200: BalloonOperationResponse,
            400: BalloonOperationResponse,
            404: BalloonOperationResponse
        }
    )
)
class BalloonsBatchViewSet(viewsets.ViewSet):
    """
    API для управления партиями баллонов

    Позволяет:
    - Создавать и обновлять партии (приёмка/отгрузка)
    - Управлять активными партиями
    - Добавлять/удалять баллоны по NFC
    - Получать статистику по партиям
    
    Поддерживает фильтрацию по типу партии через параметр batch_type:
    - l: партии приёмки
    - u: партии отгрузки
    """
    permission_classes = [IsAuthenticated]

    def get_batch_type(self, request):
        """
        Определяет тип партии из пути URL API
        """
        path = request.path.lower()
        if 'unloading' in path:
            return 'u'
        elif 'loading' in path:
            return 'l'
        return None

    @action(detail=False, methods=['get'], url_path='active')
    def is_active(self, request):
        batch_type = self.get_batch_type(request)
        if not batch_type:
            return Response(
                {"message": "Параметр batch_type обязателен (l для приёмки, u для отгрузки)"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        batches = BalloonsBatch.objects.select_related('truck', 'trailer', 'truck__type').filter(
            batch_type=batch_type, is_active=True
        )
        serializer = ActiveBatchSerializer(batches, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='last-active')
    def last_active(self, request):
        batch_type = self.get_batch_type(request)
        if not batch_type:
            return Response(
                {"message": "Параметр batch_type обязателен (l для приёмки, u для отгрузки)"},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        batch = BalloonsBatch.objects.select_related('truck', 'trailer', 'truck__type').filter(
            batch_type=batch_type, is_active=True
        ).first()
        if not batch:
            return Response(
                {"message": 'Нет активных партий'},
                status=status.HTTP_404_NOT_FOUND
            )
        serializer = BalloonsBatchSerializer(batch)
        return Response(serializer.data)

    @action(detail=True, methods=['get'], url_path='rfid-amount')
    def rfid_amount(self, request, pk=None):
        batch_type = self.get_batch_type(request)
        if not batch_type:
            return Response(
                {"message": "Параметр batch_type обязателен (l для приёмки, u для отгрузки)"},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        batch = get_object_or_404(BalloonsBatch, id=pk, batch_type=batch_type)
        serializer = BalloonAmountSerializer(batch)
        return Response(serializer.data)

    def create(self, request):
        batch_type = self.get_batch_type(request)
        if not batch_type:
            return Response(
                {"message": "Параметр batch_type обязателен (l для приёмки, u для отгрузки)"},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = BalloonsBatchSerializer(data=request.data)
        if serializer.is_valid():
            instance = serializer.save(batch_type=batch_type)
            return Response(BalloonsBatchSerializer(instance).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def partial_update(self, request, pk=None):
        batch_type = self.get_batch_type(request)
        if not batch_type:
            return Response(
                {"message": "Параметр batch_type обязателен (l для приёмки, u для отгрузки)"},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        batch = get_object_or_404(BalloonsBatch, id=pk, batch_type=batch_type)

        # Проверяем, закрывается ли партия (is_active меняется с True на False)
        is_closing = batch.is_active and not request.data.get('is_active', True)
        if is_closing:
            request.data['completed_at'] = timezone.now()
            
            # Если у партии есть ttn_id, закрываем ТТН в Мириаде
            if batch.ttn_id:
                success = close_ttn_in_miriada(batch.ttn_id)
                if not success:
                    logger.warning(f"Не удалось закрыть ТТН {batch.ttn_id} в Мириаде при закрытии партии {batch.id}")

        serializer = BalloonsBatchSerializer(batch, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['patch'], url_path='add-balloon')
    def add_balloon(self, request, pk=None):
        batch_type = self.get_batch_type(request)
        if not batch_type:
            return Response(
                {"message": "Параметр batch_type обязателен (l для приёмки, u для отгрузки)"},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        nfc = request.data.get('nfc')
        if not nfc:
            return Response(
                {"message": "Параметр 'nfc' обязателен"},
                status=status.HTTP_400_BAD_REQUEST
            )

        batch = get_object_or_404(BalloonsBatch, id=pk, batch_type=batch_type)
        result = batch.add_balloon(nfc)
        if result['success']:
            return Response(result, status=status.HTTP_200_OK)

        return Response({'message': result.get('message')}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['patch'], url_path='remove-balloon')
    def remove_balloon(self, request, pk=None):
        batch_type = self.get_batch_type(request)
        if not batch_type:
            return Response(
                {"message": "Параметр batch_type обязателен (l для приёмки, u для отгрузки)"},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        nfc = request.data.get('nfc')
        if not nfc:
            return Response(
                {"message": "Параметр 'nfc' обязателен"},
                status=status.HTTP_400_BAD_REQUEST
            )

        batch = get_object_or_404(BalloonsBatch, id=pk, batch_type=batch_type)
        result = batch.remove_balloon(nfc)
        if result['success']:
            return Response(result, status=status.HTTP_200_OK)

        return Response({'message': result.get('message')}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def get_active_balloon_batch(request):
    """
    Метод получения списков активных партий
    """
    today = date.today()
    loading_batches = BalloonsBatch.objects.select_related('truck', 'trailer').filter(
        batch_type='l', started_at__date=today, is_active=True
    )
    unloading_batches = BalloonsBatch.objects.select_related('truck', 'trailer').filter(
        batch_type='u', started_at__date=today, is_active=True
    )

    response = []
    for batch in loading_batches:
        response.append({
            'reader_id': batch.reader_number,
            'truck_registration_number': batch.truck.registration_number,
            'trailer_registration_number': batch.trailer.registration_number if batch.trailer else None
        })
    for batch in unloading_batches:
        response.append({
            'reader_id': batch.reader_number,
            'truck_registration_number': batch.truck.registration_number,
            'trailer_registration_number': batch.trailer.registration_number if batch.trailer else None
        })
    return JsonResponse(response, safe=False)
