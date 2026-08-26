"""API баллонов: CRUD по NFC, статистика ГНС, списки ридеров и ручные счётчики."""

"""API баллонов: CRUD по NFC, статистика ГНС, списки ридеров, ручные счётчики."""

import logging
from collections import defaultdict
from django.http import JsonResponse
from django.core.cache import cache
from rest_framework import status, viewsets, serializers
from rest_framework.response import Response
from rest_framework.decorators import api_view, action, permission_classes
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import (
    extend_schema,
    OpenApiParameter,
    OpenApiExample,
    OpenApiTypes,
    extend_schema_view,
    inline_serializer
)
from filling_station.models import Balloon, BalloonsBatch, DailyReaderCounter, TotalReadersCounter, ReaderSettings
from .serializers import BalloonSerializer
from core.api.schema import ApiErrorSerializer


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


# Схемы для Swagger
ErrorResponseSerializer = ApiErrorSerializer

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
            409: ApiErrorSerializer
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
            404: ApiErrorSerializer
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
        """Инициализирует ViewSet и локальный логгер."""
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


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_balloon_status_options(request):
    """
    Возвращает список допустимых пользовательских статусов баллона.

    Args:
        request: HTTP-запрос DRF.

    Returns:
        Response: список строк USER_STATUS_LIST.
    """
    return Response(USER_STATUS_LIST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_loading_balloon_reader_list(request):
    """
    Возвращает номера считывателей с функцией приёмки (l).

    Args:
        request: HTTP-запрос DRF.

    Returns:
        Response: список номеров ридеров.
    """
    loading_readers = ReaderSettings.objects.filter(function='l').values_list('number', flat=True)
    return Response(list(loading_readers))

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_unloading_balloon_reader_list(request):
    """
    Возвращает номера считывателей с функцией отгрузки (u).

    Args:
        request: HTTP-запрос DRF.

    Returns:
        Response: список номеров ридеров.
    """
    unloading_readers = ReaderSettings.objects.filter(function='u').values_list('number', flat=True)
    return Response(list(unloading_readers))

# --- TotalReadersCounter (ручной ввод) ---
class ManualTotalReadersCounterRequestSerializer(serializers.Serializer):
    """Тело запроса ручного ввода счётчиков пустых/полных баллонов."""

    empty = serializers.IntegerField(
        required=False,
        min_value=0,
        help_text='Ручное значение для количества пустых баллонов (total_empty)'
    )
    full = serializers.IntegerField(
        required=False,
        min_value=0,
        help_text='Ручное значение для количества полных баллонов (total_full)'
    )


class ManualTotalReadersCounterResponseSerializer(serializers.Serializer):
    """Ответ после записи ручных значений TotalReadersCounter."""

    total_empty = serializers.IntegerField()
    total_full = serializers.IntegerField()
    changed_at = serializers.DateTimeField()


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
    Записывает ручные значения TotalReadersCounter через API.

    Args:
        request: HTTP-запрос с полями empty и/или full.

    Returns:
        Response: текущие total_empty/total_full/changed_at или 400 при ошибке.
    """
    # Валидируем через DRF поля (включая min_value)
    req_serializer = ManualTotalReadersCounterRequestSerializer(data=request.data)
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

    # Очистка кеша статистики при внесении изменений
    cache.delete('get_balloon_statistic')

    return Response(
        {
            'total_empty': obj.total_empty,
            'total_full': obj.total_full,
            'changed_at': obj.changed_at,
        },
        status=status.HTTP_200_OK
    )
