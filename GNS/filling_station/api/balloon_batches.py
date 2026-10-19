"""API ViewSet партий приёмки/отгрузки баллонов и endpoint для SCADA."""

import logging

from django.db.models import Count
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import (
    extend_schema,
    extend_schema_view,
    inline_serializer,
    OpenApiExample,
    OpenApiParameter,
    OpenApiResponse,
    OpenApiTypes,
)
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.api.schema import FIELD_ERRORS_RESPONSE, MessageErrorSerializer
from filling_station.api.batch_status import batch_status_to_api, is_api_close_request
from filling_station.models import BalloonsBatch, BatchStatus
from filling_station.services.batches import (
    BATCH_CLOSE_WRITABLE_FIELDS,
    OPEN_BATCH_STATUSES,
    add_balloon_to_batch_by_nfc,
    pause_balloons_batch,
    resume_balloons_batch,
    save_and_close_balloons_batch,
)
from .serializers import (
    ActiveBatchSerializer,
    BalloonAmountSerializer,
    BalloonsBatchSerializer,
)

logger = logging.getLogger('filling_station')

BatchCloseMismatchErrorSerializer = inline_serializer(
    name='BatchCloseMismatchError',
    fields={
        'message': serializers.CharField(),
        'count_mismatch': serializers.BooleanField(),
        'amount_of_ttn': serializers.IntegerField(),
        'amount_of_rfid': serializers.IntegerField(),
        'amount_of_sensor': serializers.IntegerField(),
        'id': serializers.IntegerField(),
    },
)

BatchCloseMiriadaFailedSerializer = inline_serializer(
    name='BatchCloseMiriadaFailed',
    fields={
        'message': serializers.CharField(),
        'miriada_close_failed': serializers.BooleanField(),
        'miriada_error_message': serializers.CharField(allow_null=True),
        'id': serializers.IntegerField(),
        'status': serializers.IntegerField(
            help_text='API-enum: обычно 4=MIRIADA_ERROR',
        ),
    },
)

def _api_user(request) -> str:
    """
    Формирует строковый идентификатор пользователя для логов API.

    Args:
        request: HTTP-запрос DRF.

    Returns:
        str: ``pk:username`` или ``anonymous``.
    """
    user = getattr(request, 'user', None)
    if user is None or not getattr(user, 'is_authenticated', False):
        return 'anonymous'
    return f'{user.pk}:{user.get_username()}'


BalloonOperationResponse = inline_serializer(
    name='BalloonOperationResponse',
    fields={
        'success': serializers.BooleanField(),
        'balloon_id': serializers.CharField(allow_null=True),
        'new_count': serializers.IntegerField(),
        'message': serializers.CharField(required=False),
    }
)

ACTIVE_BALLOON_BATCH_SCADA_RESPONSE = OpenApiResponse(
    response={
        'type': 'array',
        'items': {
            'type': 'object',
            'title': 'ActiveBalloonBatchScadaItem',
            'properties': {
                'reader_id': {
                    'type': 'integer',
                    'description': 'Номер считывателя',
                },
                'truck_registration_number': {
                    'type': 'string',
                    'description': 'Рег. номер грузовика',
                },
                'trailer_registration_number': {
                    'type': 'string',
                    'description': 'Рег. номер прицепа (пустая строка, если нет)',
                },
            },
            'required': [
                'reader_id',
                'truck_registration_number',
                'trailer_registration_number',
            ],
        },
    },
    description=(
        'Массив активных партий (приёмка и отгрузка) за сегодня: '
        'reader_id и рег. номера грузовика/прицепа.'
    ),
    examples=[
                OpenApiExample(
                    'Пример',
                    value=[
                        {
                            'reader_id': 6,
                            'truck_registration_number': 'AC 5512-1',
                            'trailer_registration_number': 'A 5003K-1',
                        },
                    ],
                ),
    ],
)

_BATCH_STATUS_DOC = (
    'Статус партии (числовой enum): '
    '1=ACTIVE — в работе (RFID принимает баллоны); '
    '2=PAUSED — приостановлена (ручное добавление/удаление доступно); '
    '3=COMPLETED — завершена; '
    '4=MIRIADA_ERROR — ошибка закрытия ТТН в Мириаде. '
    '0=UNSPECIFIED не используется.'
)


def _balloon_operation_error_status(message: str | None) -> int:
    """
    HTTP-статус для отказа add/remove balloon.

    Бизнес-отказы не должны уходить как 500: иначе django.request
    пишет Internal Server Error в stderr NSSM.

    Args:
        message: текст отказа из ``BalloonsBatch.add_balloon`` / ``remove_balloon``.

    Returns:
        int: 409 при дубликате в партии, 404 если метка не найдена,
        500 только для непредвиденной ошибки сервера, иначе 400.
    """
    text = message or ''
    if 'уже в партии' in text:
        return status.HTTP_409_CONFLICT
    if 'не найден' in text:
        return status.HTTP_404_NOT_FOUND
    if text.startswith('Ошибка сервера'):
        return status.HTTP_500_INTERNAL_SERVER_ERROR
    return status.HTTP_400_BAD_REQUEST


def _api_error_payload(payload):
    """
    Нормализует payload ошибки: статус партии переводит в API-enum.

    Args:
        payload: тело ошибки (dict или иное).

    Returns:
        То же значение с ``status`` в числовом виде при наличии ключа.
    """
    if isinstance(payload, dict) and 'status' in payload:
        return {**payload, 'status': batch_status_to_api(payload['status'])}
    return payload


def _apply_batch_close_writable_fields(batch: BalloonsBatch, data) -> tuple[bool, object]:
    """
    Применяет writable-поля партии перед закрытием через сериализатор.

    Args:
        batch: партия для обновления.
        data: тело запроса (dict-like).

    Returns:
        tuple: (успех, None) или (False, ошибки сериализатора).
    """
    payload = {
        key: value
        for key, value in (data or {}).items()
        if key in BATCH_CLOSE_WRITABLE_FIELDS
    }
    if not payload:
        return True, None
    serializer = BalloonsBatchSerializer(batch, data=payload, partial=True)
    if not serializer.is_valid():
        return False, serializer.errors
    serializer.save()
    batch.refresh_from_db()
    return True, None


def _close_batch_response(batch: BalloonsBatch, data, *, log_prefix: str, api_user: str):
    """
    Применяет поля, закрывает партию и формирует HTTP-ответ.

    Args:
        batch: партия для закрытия.
        data: тело запроса.
        log_prefix: префикс для логов.
        api_user: идентификатор пользователя API.

    Returns:
        Response: 200 с данными партии или 400/502 при ошибке.
    """
    fields_ok, field_errors = _apply_batch_close_writable_fields(batch, data)
    if not fields_ok:
        logger.warning(
            f"{log_prefix} validation failed: user={api_user}, batch_id={batch.id}, "
            f"errors={field_errors}"
        )
        return Response(field_errors, status=status.HTTP_400_BAD_REQUEST)

    success, error_payload = save_and_close_balloons_batch(batch)
    if not success:
        logger.warning(
            f"{log_prefix} failed: user={api_user}, batch_id={batch.id}, "
            f"error={error_payload}"
        )
        error_payload = _api_error_payload(error_payload)
        if isinstance(error_payload, dict) and error_payload.get('miriada_close_failed'):
            return Response(error_payload, status=status.HTTP_502_BAD_GATEWAY)
        return Response(error_payload, status=status.HTTP_400_BAD_REQUEST)

    logger.info(f"{log_prefix} ok: user={api_user}, batch_id={batch.id}")
    return Response(BalloonsBatchSerializer(batch).data)


@extend_schema_view(
    is_active=extend_schema(
        tags=['Партии баллонов'],
        summary='Получить незавершённые партии',
        description=(
            'Список партий, которые ещё не завершены успешно: '
            'status ∈ {1=ACTIVE, 2=PAUSED, 4=MIRIADA_ERROR}. '
            f'{_BATCH_STATUS_DOC}'
        ),
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
            400: MessageErrorSerializer,
        }
    ),
    last_active=extend_schema(
        tags=['Партии баллонов'],
        summary='Получить текущую активную партию',
        description=(
            'Последняя партия со статусом 1=ACTIVE (принимает RFID). '
            'Партии в 2=PAUSED или 4=MIRIADA_ERROR не возвращаются.'
        ),
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
            404: MessageErrorSerializer,
        }
    ),
    rfid_amount=extend_schema(
        tags=['Партии баллонов'],
        summary='Количество баллонов по RFID',
        description=(
            'Количество баллонов в партии: RFID, оптический датчик и электронная ТТН. '
            'Также возвращает `error_balloons` — баллоны с ошибкой отправки статуса в Мириаду.'
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
            200: BalloonAmountSerializer,
            404: MessageErrorSerializer,
        }
    ),
    create=extend_schema(
        tags=['Партии баллонов'],
        summary='Создать новую партию',
        description=(
            'Создание партии с привязкой к ТТН. Обязательно поле `amount_of_ttn`. '
            'По умолчанию `status`: 1 (ACTIVE). При создании активной партии другие '
            'активные партии на том же считывателе за сегодня автоматически '
            'переводятся в 2 (PAUSED).'
        ),
        request=BalloonsBatchSerializer,
        responses={
            201: BalloonsBatchSerializer,
            400: FIELD_ERRORS_RESPONSE,
        }
    ),
    partial_update=extend_schema(
        tags=['Партии баллонов'],
        summary='Обновить или завершить партию',
        description=(
            'Частичное обновление полей партии (счётчики, транспорт, ТТН и т.д.).\n\n'
            '**Завершение партии:** передайте `"status": 3` (COMPLETED). '
            'Статусы баллонов с ошибками повторно отправляются в Мириаду, '
            'затем проверяется совпадение RFID с ТТН и отсутствие ошибок, '
            'после чего вызывается закрытие ТТН (`closettn`). '
            'Доступно для статусов 1=ACTIVE, 2=PAUSED и 4=MIRIADA_ERROR. '
            'При ошибке closettn партия переходит в 4=MIRIADA_ERROR (ответ HTTP 502).\n\n'
            'Устаревший способ (обратная совместимость): `"is_active": false`. '
            'Поле `is_active` удалено из модели — используйте `status`.\n\n'
            '**400 при закрытии** может быть: ошибки валидации полей, '
            '`count_mismatch`, `balloon_status_errors` или `{"message": "..."}`.'
        ),
        parameters=[
            OpenApiParameter(
                name='id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='ID партии',
            ),
        ],
        request=BalloonsBatchSerializer,
        responses={
            200: BalloonsBatchSerializer,
            400: BatchCloseMismatchErrorSerializer,
            404: MessageErrorSerializer,
            502: BatchCloseMiriadaFailedSerializer,
        }
    ),
    add_balloon=extend_schema(
        tags=['Партии баллонов'],
        summary='Добавить баллон в партию',
        description=(
            'Добавление баллона по NFC-метке. Статус сразу отправляется в Мириаду. '
            'Ошибки Мириады сохраняются на баллоне и доступны в GET .../rfid-amount/ '
            '(`error_balloons`). Добавление в партию успешно даже при ошибке Мириады. '
            'Доступно для статусов 1=ACTIVE, 2=PAUSED и 4=MIRIADA_ERROR.'
        ),
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
            400: MessageErrorSerializer,
            404: MessageErrorSerializer,
            409: MessageErrorSerializer,
        }
    ),
    remove_balloon=extend_schema(
        tags=['Партии баллонов'],
        summary='Удалить баллон из партии',
        description=(
            'Удаление баллона по NFC-метке. '
            'Доступно для статусов 1=ACTIVE, 2=PAUSED и 4=MIRIADA_ERROR.'
        ),
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
            400: MessageErrorSerializer,
            404: MessageErrorSerializer,
        }
    ),
    retry_close=extend_schema(
        tags=['Партии баллонов'],
        summary='Повторно завершить партию',
        description=(
            'Сохраняет данные партии, повторно отправляет в Мириаду только баллоны '
            'с ошибками, проверяет совпадение RFID с ТТН и закрывает ТТН (`closettn`). '
            'Доступно для статусов 1=ACTIVE, 2=PAUSED и 4=MIRIADA_ERROR '
            '(повтор после ошибки Мириады).'
        ),
        request=BalloonsBatchSerializer,
        parameters=[
            OpenApiParameter(
                name='id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='ID партии'
            )
        ],
        responses={
            200: BalloonsBatchSerializer,
            400: BatchCloseMismatchErrorSerializer,
            404: MessageErrorSerializer,
            502: BatchCloseMiriadaFailedSerializer,
        }
    ),
    pause=extend_schema(
        tags=['Партии баллонов'],
        summary='Приостановить партию',
        description=(
            'Переводит партию из 1=ACTIVE в 2=PAUSED. '
            'RFID и датчик перестают добавлять баллоны; '
            'ручное добавление и удаление остаётся доступным.'
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
            200: BalloonsBatchSerializer,
            400: MessageErrorSerializer,
            404: MessageErrorSerializer,
        }
    ),
    resume=extend_schema(
        tags=['Партии баллонов'],
        summary='Возобновить партию',
        description=(
            'Переводит партию из 2=PAUSED в 1=ACTIVE. '
            'Другие активные партии на том же считывателе за сегодня '
            'автоматически переводятся в 2=PAUSED.'
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
            200: BalloonsBatchSerializer,
            400: MessageErrorSerializer,
            404: MessageErrorSerializer,
        }
    ),
)
class BalloonsBatchViewSet(viewsets.ViewSet):
    """API партий приёмки/отгрузки баллонов. Состояние задаётся полем `status`."""
    permission_classes = [IsAuthenticated]
    serializer_class = BalloonsBatchSerializer

    def get_batch_type(self, request):
        """
        Определяет тип партии по пути URL (loading/unloading).

        Args:
            request: HTTP-запрос DRF.

        Returns:
            str | None: ``l``, ``u`` или None, если тип не распознан.
        """
        path = request.path.lower()
        if 'unloading' in path:
            return 'u'
        if 'loading' in path:
            return 'l'
        return None

    @action(detail=False, methods=['get'], url_path='active')
    def is_active(self, request):
        """
        Возвращает список незавершённых партий выбранного типа.

        Args:
            request: HTTP-запрос DRF.

        Returns:
            Response: список ActiveBatchSerializer или 400 без batch_type.
        """
        batch_type = self.get_batch_type(request)
        if not batch_type:
            return Response(
                {"message": "Параметр batch_type обязателен (l для приёмки, u для отгрузки)"},
                status=status.HTTP_400_BAD_REQUEST
            )

        batches = BalloonsBatch.objects.select_related('truck', 'trailer', 'truck__type').annotate(
            annotated_rfid_count=Count('balloon_list', distinct=True),
        ).filter(
            batch_type=batch_type,
            status__in=OPEN_BATCH_STATUSES,
        )

        serializer = ActiveBatchSerializer(batches, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='last-active')
    def last_active(self, request):
        """
        Возвращает последнюю партию со статусом ACTIVE.

        Args:
            request: HTTP-запрос DRF.

        Returns:
            Response: данные партии, 404 если активных нет, 400 без batch_type.
        """
        batch_type = self.get_batch_type(request)
        if not batch_type:
            return Response(
                {"message": "Параметр batch_type обязателен (l для приёмки, u для отгрузки)"},
                status=status.HTTP_400_BAD_REQUEST
            )

        batch = BalloonsBatch.objects.select_related('truck', 'trailer', 'truck__type').annotate(
            annotated_rfid_count=Count('balloon_list', distinct=True),
        ).filter(
            batch_type=batch_type,
            status=BatchStatus.ACTIVE,
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
        """
        Возвращает счётчики RFID/датчика/ТТН для партии.

        Args:
            request: HTTP-запрос DRF.
            pk: ID партии.

        Returns:
            Response: BalloonAmountSerializer или ошибка 400/404.
        """
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
        """
        Создаёт новую партию указанного типа.

        Args:
            request: HTTP-запрос с телом BalloonsBatchSerializer.

        Returns:
            Response: 201 с данными партии или 400 при ошибке валидации.
        """
        batch_type = self.get_batch_type(request)
        if not batch_type:
            return Response(
                {"message": "Параметр batch_type обязателен (l для приёмки, u для отгрузки)"},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = BalloonsBatchSerializer(data=request.data)
        if serializer.is_valid():
            instance = serializer.save(batch_type=batch_type)
            logger.info(
                f"API create batch: user={_api_user(request)}, batch_id={instance.id}, "
                f"batch_type={batch_type}, ttn_id={instance.ttn_id}, "
                f"amount_of_ttn={instance.amount_of_ttn}, reader_number={instance.reader_number}, "
                f"truck={instance.truck_id}"
            )
            return Response(BalloonsBatchSerializer(instance).data, status=status.HTTP_201_CREATED)
        logger.warning(
            f"API create batch failed: user={_api_user(request)}, batch_type={batch_type}, "
            f"errors={serializer.errors}, data={request.data}"
        )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def partial_update(self, request, pk=None):
        """
        Частично обновляет партию или закрывает её при status=COMPLETED.

        Args:
            request: HTTP-запрос с частичными полями партии.
            pk: ID партии.

        Returns:
            Response: обновлённые данные, 400/502 при ошибке закрытия.
        """
        batch_type = self.get_batch_type(request)
        if not batch_type:
            return Response(
                {"message": "Параметр batch_type обязателен (l для приёмки, u для отгрузки)"},
                status=status.HTTP_400_BAD_REQUEST
            )

        batch = get_object_or_404(BalloonsBatch, id=pk, batch_type=batch_type)

        is_closing = (
            batch.status in (
                BatchStatus.ACTIVE,
                BatchStatus.PAUSED,
                BatchStatus.MIRIADA_ERROR,
            )
            and (
                is_api_close_request(request.data)
                or ('is_active' in request.data and not request.data.get('is_active', True))
            )
        )
        if is_closing:
            logger.info(
                f"API close batch: user={_api_user(request)}, batch_id={batch.id}, "
                f"ttn_id={batch.ttn_id}, amount_of_rfid={batch.rfid_balloon_count()}, "
                f"amount_of_ttn={batch.amount_of_ttn}, data={dict(request.data)}"
            )
            return _close_batch_response(
                batch,
                request.data,
                log_prefix='API close batch',
                api_user=_api_user(request),
            )

        serializer = BalloonsBatchSerializer(batch, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            logger.info(
                f"API update batch: user={_api_user(request)}, batch_id={batch.id}, "
                f"data={dict(request.data)}"
            )
            return Response(serializer.data)
        logger.warning(
            f"API update batch failed: user={_api_user(request)}, batch_id={batch.id}, "
            f"errors={serializer.errors}"
        )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], url_path='retry-close')
    def retry_close(self, request, pk=None):
        """
        Повторно сохраняет и закрывает партию после ошибки Мириады.

        Args:
            request: HTTP-запрос с опциональными полями партии.
            pk: ID партии.

        Returns:
            Response: данные партии или 400/502 при ошибке.
        """
        batch_type = self.get_batch_type(request)
        if not batch_type:
            return Response(
                {"message": "Параметр batch_type обязателен (l для приёмки, u для отгрузки)"},
                status=status.HTTP_400_BAD_REQUEST
            )

        batch = get_object_or_404(BalloonsBatch, id=pk, batch_type=batch_type)

        if batch.status not in (BatchStatus.ACTIVE, BatchStatus.PAUSED, BatchStatus.MIRIADA_ERROR):
            return Response(
                {"message": "Партия уже завершена и не содержит ошибок"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        logger.info(
            f"API retry-close: user={_api_user(request)}, batch_id={batch.id}, "
            f"ttn_id={batch.ttn_id}, amount_of_rfid={batch.rfid_balloon_count()}, "
            f"amount_of_ttn={batch.amount_of_ttn}"
        )
        return _close_batch_response(
            batch,
            request.data,
            log_prefix='API retry-close',
            api_user=_api_user(request),
        )

    @action(detail=True, methods=['patch'], url_path='add-balloon')
    def add_balloon(self, request, pk=None):
        """
        Добавляет баллон в партию по NFC-метке.

        Args:
            request: HTTP-запрос с полем ``nfc``.
            pk: ID партии.

        Returns:
            Response: результат операции или ошибка 400/404/409.
        """
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
        if not batch.accepts_manual_edits():
            return Response(
                {'message': 'Партия не принимает изменения в текущем статусе'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        result = add_balloon_to_batch_by_nfc(batch, nfc)
        if result['success']:
            batch.refresh_from_db()
            logger.info(
                f"API add-balloon: user={_api_user(request)}, batch_id={batch.id}, "
                f"nfc={nfc}, amount_of_rfid={batch.rfid_balloon_count()}"
            )
            return Response(result, status=status.HTTP_200_OK)

        logger.warning(
            f"API add-balloon failed: user={_api_user(request)}, batch_id={batch.id}, "
            f"nfc={nfc}, message={result.get('message')}"
        )
        return Response(
            {'message': result.get('message')},
            status=_balloon_operation_error_status(result.get('message')),
        )

    @action(detail=True, methods=['patch'], url_path='remove-balloon')
    def remove_balloon(self, request, pk=None):
        """
        Удаляет баллон из партии по NFC-метке.

        Args:
            request: HTTP-запрос с полем ``nfc``.
            pk: ID партии.

        Returns:
            Response: результат операции или ошибка 400/404.
        """
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
        if not batch.accepts_manual_edits():
            return Response(
                {'message': 'Партия не принимает изменения в текущем статусе'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        result = batch.remove_balloon(nfc)
        if result['success']:
            batch.refresh_from_db()
            logger.info(
                f"API remove-balloon: user={_api_user(request)}, batch_id={batch.id}, "
                f"nfc={nfc}, amount_of_rfid={batch.rfid_balloon_count()}"
            )
            return Response(result, status=status.HTTP_200_OK)

        logger.warning(
            f"API remove-balloon failed: user={_api_user(request)}, batch_id={batch.id}, "
            f"nfc={nfc}, message={result.get('message')}"
        )
        return Response(
            {'message': result.get('message')},
            status=_balloon_operation_error_status(result.get('message')),
        )

    @action(detail=True, methods=['post'], url_path='pause')
    def pause(self, request, pk=None):
        """
        Приостанавливает активную партию (ACTIVE → PAUSED).

        Args:
            request: HTTP-запрос DRF.
            pk: ID партии.

        Returns:
            Response: данные партии или 400 при недопустимом статусе.
        """
        batch_type = self.get_batch_type(request)
        if not batch_type:
            return Response(
                {"message": "Параметр batch_type обязателен (l для приёмки, u для отгрузки)"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        batch = get_object_or_404(BalloonsBatch, id=pk, batch_type=batch_type)
        success, message = pause_balloons_batch(batch)
        if not success:
            return Response({'message': message}, status=status.HTTP_400_BAD_REQUEST)

        logger.info(f"API pause batch: user={_api_user(request)}, batch_id={batch.id}")
        batch.refresh_from_db()
        return Response(BalloonsBatchSerializer(batch).data)

    @action(detail=True, methods=['post'], url_path='resume')
    def resume(self, request, pk=None):
        """
        Возобновляет приостановленную партию (PAUSED → ACTIVE).

        Args:
            request: HTTP-запрос DRF.
            pk: ID партии.

        Returns:
            Response: данные партии или 400 при недопустимом статусе.
        """
        batch_type = self.get_batch_type(request)
        if not batch_type:
            return Response(
                {"message": "Параметр batch_type обязателен (l для приёмки, u для отгрузки)"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        batch = get_object_or_404(BalloonsBatch, id=pk, batch_type=batch_type)
        success, message = resume_balloons_batch(batch)
        if not success:
            return Response({'message': message}, status=status.HTTP_400_BAD_REQUEST)

        logger.info(f"API resume batch: user={_api_user(request)}, batch_id={batch.id}")
        batch.refresh_from_db()
        return Response(BalloonsBatchSerializer(batch).data)


@extend_schema(
    tags=['Партии баллонов'],
    summary='Активные партии для SCADA',
    description=(
        'Список партий со статусом 1=ACTIVE за сегодня для приёмки и отгрузки. '
        'Используется SCADA: номер считывателя и регистрационные номера транспорта.'
    ),
    responses={200: ACTIVE_BALLOON_BATCH_SCADA_RESPONSE},
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_active_balloon_batch(request):
    """
    Возвращает списки активных партий приёмки/отгрузки за сегодня для SCADA.

    Args:
        request: HTTP-запрос DRF.

    Returns:
        JsonResponse: список объектов с reader_id и номерами транспорта.
    """
    today = timezone.localdate()
    loading_batches = BalloonsBatch.objects.select_related('truck', 'trailer').filter(
        batch_type='l', started_at__date=today, status=BatchStatus.ACTIVE,
    )
    unloading_batches = BalloonsBatch.objects.select_related('truck', 'trailer').filter(
        batch_type='u', started_at__date=today, status=BatchStatus.ACTIVE,
    )

    response = []
    for batch in loading_batches:
        response.append({
            'reader_id': batch.reader_number,
            'truck_registration_number': batch.truck.registration_number,
            'trailer_registration_number': (
                batch.trailer.registration_number if batch.trailer else ''
            )
        })
    for batch in unloading_batches:
        response.append({
            'reader_id': batch.reader_number,
            'truck_registration_number': batch.truck.registration_number,
            'trailer_registration_number': (
                batch.trailer.registration_number if batch.trailer else ''
            )
        })
    return JsonResponse(response, safe=False)
