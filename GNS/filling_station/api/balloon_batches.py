from django.db.models import Q
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

from filling_station.models import BalloonsBatch
from filling_station.services import add_balloon_to_batch_by_nfc, save_and_close_balloons_batch
from .serializers import (
    ActiveBatchSerializer,
    BalloonAmountSerializer,
    BalloonsBatchSerializer,
)

logger = logging.getLogger('filling_station')


def _api_user(request) -> str:
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
            404: OpenApiTypes.OBJECT
        }
    ),
    create=extend_schema(
        tags=['Партии баллонов'],
        summary='Создать новую партию',
        description='Создание новой партии баллонов с привязкой к ТТН и количеством баллонов по электронной ТТН',
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
        description='Добавление баллона в партию по NFC метке. Статус в Мириаду отправляется при закрытии партии.',
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
    ),
    retry_close=extend_schema(
        tags=['Партии баллонов'],
        summary='Завершить партию',
        description=(
            'Сохраняет данные партии, отправляет статусы всех баллонов в Мириаду '
            'и закрывает ТТН. Завершение возможно, только если количество RFID '
            'совпадает с количеством по электронной ТТН. '
            'Доступно для активных партий (первичное завершение и повтор после ошибки Мириады).'
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
            400: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT,
            502: OpenApiTypes.OBJECT,
        }
    )
)
class BalloonsBatchViewSet(viewsets.ViewSet):
    """API для управления партиями баллонов приёмки и отгрузки."""
    permission_classes = [IsAuthenticated]

    def get_batch_type(self, request):
        path = request.path.lower()
        if 'unloading' in path:
            return 'u'
        if 'loading' in path:
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
            batch_type=batch_type
        ).filter(Q(is_active=True) | Q(miriada_close_failed=True))

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
        batch_type = self.get_batch_type(request)
        if not batch_type:
            return Response(
                {"message": "Параметр batch_type обязателен (l для приёмки, u для отгрузки)"},
                status=status.HTTP_400_BAD_REQUEST
            )

        batch = get_object_or_404(BalloonsBatch, id=pk, batch_type=batch_type)

        is_closing = batch.is_active and not request.data.get('is_active', True)
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
        batch_type = self.get_batch_type(request)
        if not batch_type:
            return Response(
                {"message": "Параметр batch_type обязателен (l для приёмки, u для отгрузки)"},
                status=status.HTTP_400_BAD_REQUEST
            )

        batch = get_object_or_404(BalloonsBatch, id=pk, batch_type=batch_type)

        if not batch.is_active and not batch.miriada_close_failed:
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
            if isinstance(error_payload, dict) and error_payload.get('miriada_close_failed'):
                return Response(error_payload, status=status.HTTP_502_BAD_GATEWAY)
            return Response(error_payload, status=status.HTTP_400_BAD_REQUEST)
        logger.info(f"API retry-close ok: user={_api_user(request)}, batch_id={batch.id}")
        return Response(response_data)

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


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_active_balloon_batch(request):
    """Метод получения списков активных партий."""
    today = timezone.localdate()
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
