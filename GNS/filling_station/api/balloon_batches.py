"""API ViewSet партий приёмки/отгрузки баллонов и endpoint для SCADA."""

from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.utils import (
    extend_schema,
    extend_schema_view,
    inline_serializer,
    OpenApiParameter,
    OpenApiTypes,
)
import logging

from filling_station.models import BalloonsBatch, BatchStatus
from filling_station.api.batch_status import batch_status_to_api, is_api_close_request
from filling_station.services import (
    add_balloon_to_batch_by_nfc,
    pause_balloons_batch,
    resume_balloons_batch,
    save_and_close_balloons_batch,
)
from filling_station.services.batches import OPEN_BATCH_STATUSES
from core.api.schema import ApiErrorSerializer
from .serializers import (
    ActiveBatchSerializer,
    BalloonAmountSerializer,
    BalloonsBatchSerializer,
)

logger = logging.getLogger('filling_station')


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
        'error': serializers.CharField()
    }
)

_BATCH_STATUS_DOC = (
    'Статус партии (числовой enum): '
    '1=ACTIVE — в работе (RFID принимает баллоны); '
    '2=PAUSED — приостановлена (ручное добавление/удаление доступно); '
    '3=COMPLETED — завершена; '
    '4=MIRIADA_ERROR — ошибка закрытия ТТН в Мириаде. '
    '0=UNSPECIFIED не используется.'
)


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
            400: ApiErrorSerializer,
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
            404: ApiErrorSerializer
        }
    ),
    rfid_amount=extend_schema(
        tags=['Партии баллонов'],
        summary='Количество баллонов по RFID',
        description='Количество баллонов в партии: RFID, оптический датчик и электронная ТТН',
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
            404: ApiErrorSerializer
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
            400: ApiErrorSerializer
        }
    ),
    partial_update=extend_schema(
        tags=['Партии баллонов'],
        summary='Обновить или завершить партию',
        description=(
            'Частичное обновление полей партии (счётчики, транспорт, ТТН и т.д.).\n\n'
            '**Завершение партии:** передайте `"status": 3` (COMPLETED). '
            'Отправляются статусы баллонов в Мириаду и закрывается ТТН. '
            'Доступно для статусов 1=ACTIVE и 2=PAUSED. '
            'При ошибке Мириады партия переходит в 4=MIRIADA_ERROR (ответ HTTP 502).\n\n'
            'Устаревший способ (обратная совместимость): `"is_active": false`. '
            'Поле `is_active` удалено из модели — используйте `status`.'
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
            400: ApiErrorSerializer,
            404: ApiErrorSerializer,
            502: ApiErrorSerializer,
        }
    ),
    add_balloon=extend_schema(
        tags=['Партии баллонов'],
        summary='Добавить баллон в партию',
        description=(
            'Добавление баллона по NFC-метке. Статус в Мириаду отправляется при закрытии партии. '
            'Доступно для статусов 1=ACTIVE и 2=PAUSED.'
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
            400: BalloonOperationResponse,
            404: BalloonOperationResponse,
            409: BalloonOperationResponse
        }
    ),
    remove_balloon=extend_schema(
        tags=['Партии баллонов'],
        summary='Удалить баллон из партии',
        description=(
            'Удаление баллона по NFC-метке. '
            'Доступно для статусов 1=ACTIVE и 2=PAUSED.'
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
            400: BalloonOperationResponse,
            404: BalloonOperationResponse
        }
    ),
    retry_close=extend_schema(
        tags=['Партии баллонов'],
        summary='Повторно завершить партию',
        description=(
            'Сохраняет данные партии, отправляет статусы баллонов в Мириаду '
            'и закрывает ТТН. Завершение возможно только если количество RFID '
            'совпадает с количеством по электронной ТТН. '
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
            400: ApiErrorSerializer,
            404: ApiErrorSerializer,
            502: ApiErrorSerializer,
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
            400: ApiErrorSerializer,
            404: ApiErrorSerializer,
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
            400: ApiErrorSerializer,
            404: ApiErrorSerializer,
        }
    ),
)
class BalloonsBatchViewSet(viewsets.ViewSet):
    """API партий приёмки/отгрузки баллонов. Состояние задаётся полем `status`."""
    permission_classes = [IsAuthenticated]

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

        batches = BalloonsBatch.objects.select_related('truck', 'trailer', 'truck__type').filter(
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

        batch = BalloonsBatch.objects.select_related('truck', 'trailer', 'truck__type').filter(
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
            batch.status in (BatchStatus.ACTIVE, BatchStatus.PAUSED)
            and (
                is_api_close_request(request.data)
                or ('is_active' in request.data and not request.data.get('is_active', True))
            )
        )
        if is_closing:
            logger.info(
                f"API close batch: user={_api_user(request)}, batch_id={batch.id}, "
                f"ttn_id={batch.ttn_id}, amount_of_rfid={batch.amount_of_rfid}, "
                f"amount_of_ttn={batch.amount_of_ttn}, data={dict(request.data)}"
            )
            success, error_payload, response_data = save_and_close_balloons_batch(batch, request.data)
            if not success:
                logger.warning(
                    f"API close batch failed: user={_api_user(request)}, batch_id={batch.id}, "
                    f"error={error_payload}"
                )
                error_payload = _api_error_payload(error_payload)
                if isinstance(error_payload, dict) and error_payload.get('miriada_close_failed'):
                    return Response(error_payload, status=status.HTTP_502_BAD_GATEWAY)
                return Response(error_payload, status=status.HTTP_400_BAD_REQUEST)
            logger.info(f"API close batch ok: user={_api_user(request)}, batch_id={batch.id}")
            return Response(response_data)

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
            f"ttn_id={batch.ttn_id}, amount_of_rfid={batch.amount_of_rfid}, "
            f"amount_of_ttn={batch.amount_of_ttn}"
        )
        success, error_payload, response_data = save_and_close_balloons_batch(batch, request.data)
        if not success:
            logger.warning(
                f"API retry-close failed: user={_api_user(request)}, batch_id={batch.id}, "
                f"error={error_payload}"
            )
            error_payload = _api_error_payload(error_payload)
            if isinstance(error_payload, dict) and error_payload.get('miriada_close_failed'):
                return Response(error_payload, status=status.HTTP_502_BAD_GATEWAY)
            return Response(error_payload, status=status.HTTP_400_BAD_REQUEST)
        logger.info(f"API retry-close ok: user={_api_user(request)}, batch_id={batch.id}")
        return Response(response_data)

    @action(detail=True, methods=['patch'], url_path='add-balloon')
    def add_balloon(self, request, pk=None):
        """
        Добавляет баллон в партию по NFC-метке.

        Args:
            request: HTTP-запрос с полем ``nfc``.
            pk: ID партии.

        Returns:
            Response: результат операции или ошибка 400/500.
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
                f"nfc={nfc}, amount_of_rfid={batch.amount_of_rfid}"
            )
            return Response(result, status=status.HTTP_200_OK)

        logger.warning(
            f"API add-balloon failed: user={_api_user(request)}, batch_id={batch.id}, "
            f"nfc={nfc}, message={result.get('message')}"
        )
        return Response({'message': result.get('message')}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['patch'], url_path='remove-balloon')
    def remove_balloon(self, request, pk=None):
        """
        Удаляет баллон из партии по NFC-метке.

        Args:
            request: HTTP-запрос с полем ``nfc``.
            pk: ID партии.

        Returns:
            Response: результат операции или ошибка 400/500.
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
                f"nfc={nfc}, amount_of_rfid={batch.amount_of_rfid}"
            )
            return Response(result, status=status.HTTP_200_OK)

        logger.warning(
            f"API remove-balloon failed: user={_api_user(request)}, batch_id={batch.id}, "
            f"nfc={nfc}, message={result.get('message')}"
        )
        return Response({'message': result.get('message')}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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
    responses={200: OpenApiTypes.OBJECT},
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
