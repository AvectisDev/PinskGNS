import logging
from collections import defaultdict
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
from filling_station.models import Balloon, Reader, BalloonsLoadingBatch, BalloonsUnloadingBatch, ReaderSettings
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
    update_by_reader=extend_schema(
        tags=['Баллоны'],
        summary='Обновить данные баллона через считыватель',
        description='Обновление данных баллона при срабатывании RFID считывателя',
        request=inline_serializer(
            name='UpdateByReaderRequest',
            fields={
                'nfc_tag': serializers.CharField(allow_null=True),
                'reader_number': serializers.IntegerField()
            }
        ),
        responses={
            200: UpdateByReaderResponseSerializer,
            400: ErrorResponseSerializer
        },
        examples=[
            OpenApiExample(
                'Запрос с NFC меткой',
                value={
                    "nfc_tag": "1234567890ABCDEF",
                    "reader_number": 1
                },
                request_only=True
            ),
            OpenApiExample(
                'Запрос без NFC метки',
                value={
                    "nfc_tag": None,
                    "reader_number": 6
                },
                request_only=True
            ),
            OpenApiExample(
                'Успешный ответ',
                value={
                    "status": "Данные обновлены",
                    "balloon": {
                        "nfc_tag": "1234567890ABCDEF",
                        "serial_number": "B12345",
                        "size": 50,
                        "netto": 18.5,
                        "brutto": 40.2,
                        "status": "На складе",
                        "filling_status": True
                    }
                },
                response_only=True
            ),
            OpenApiExample(
                'Ответ без NFC',
                value={
                    "status": "Добавлен баллон без NFC",
                    "balloon": None
                },
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
        balloon = get_object_or_404(Balloon, nfc_tag=nfc_tag)
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
        balloons = Balloon.objects.filter(serial_number=serial_number)
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
            reader_stats = Reader.get_common_stats_for_gns()
            loading_batches = BalloonsLoadingBatch.get_common_stats_for_gns()
            unloading_batches = BalloonsUnloadingBatch.get_common_stats_for_gns()
            balloons_stat = Balloon.get_balloons_stats()

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


    @action(detail=False, methods=['post'], url_path='update-by-reader')
    def update_by_reader(self, request):
        """
        Обновление данных баллона при срабатывании RFID считывателя.
        Логика работы:
        1. Если передан nfc_tag - обновляем данные соответствующего баллона
        2. Если nfc_tag отсутствует - создаем запись о баллоне без метки
        3. Для определенных считывателей (2-6, 8) отправляет статус в Мириаду
        Args:
            request: HTTP запрос с параметрами:
                - reader_number (int): Номер считывателя (обязательный)
                - nfc_tag (str, optional): NFC метка баллона
        Returns:
            Response: Статус операции и данные баллона (если есть)
        Raises:
            HTTP 400: Если не указан номер считывателя
        """
        reader_number = request.data.get('reader_number')
        if reader_number is None:
            self.logger.error("Номер ридера отсутствует в теле запроса")
            return Response({"error": "Номер считывателя отсутствует в теле запроса"}, status=400)

        nfc_tag = request.data.get('nfc_tag')
        # Ситуация, когда нет метки
        if nfc_tag is None:
            services.processing_request_without_nfc(reader_number)
            return Response({"status": "Добавлен баллон без NFC"}, status=200)

        # Ситуация, когда есть метка
        balloon, reader = services.processing_request_with_nfc(nfc_tag=nfc_tag, reader_number=reader_number)

        # Отправка статусов в Мириаду
        if (2 <= reader.number <= 6) or reader.number == 8:
            services.send_status_to_miriada(reader=reader.number, nfc_tag=balloon.nfc_tag)

        serializer = BalloonSerializer(balloon)
        return Response(serializer.data)


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
        return Response(status=status.HTTP_409_CONFLICT)


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
        balloon = get_object_or_404(Balloon, nfc_tag=pk)

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
