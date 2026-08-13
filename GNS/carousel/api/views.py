from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets, serializers
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from drf_spectacular.utils import (
    extend_schema,
    extend_schema_view,
    inline_serializer,
    OpenApiTypes,
    OpenApiExample,
    OpenApiParameter
)
import logging
from carousel.models import CarouselSettings
from carousel.services import (
    CarouselPostNotFoundError,
    UnsupportedCarouselRequestError,
    process_carousel_data,
)
from .serializers import CarouselSerializer, CarouselSettingsSerializer


logger = logging.getLogger('filling_station')


@extend_schema_view(
    get_parameter=extend_schema(
        tags=['Карусель'],
        summary='Получить параметры карусели',
        description='Получение настроек карусели наполнения баллонов',
        responses={
            200: CarouselSettingsSerializer,
            404: OpenApiTypes.OBJECT
        }
    ),
    partial_update=extend_schema(
        tags=['Карусель'],
        summary='Обновить параметры карусели',
        description='Частичное обновление настроек карусели',
        request=CarouselSettingsSerializer,
        responses={
            200: CarouselSettingsSerializer,
            400: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT
        },
        parameters=[
            OpenApiParameter(
                name='pk',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='ID карусели'
            )
        ]
    ),
    update_from_carousel=extend_schema(
        tags=['Карусель'],
        summary='Обновить данные от карусели',
        description='Получение данных от постов наполнения карусели. '
                    'Поддерживает два типа запросов: 0x7a (данные о баллоне) и 0x70 (обновление веса).',
        request=inline_serializer(
            name='CarouselUpdateRequest',
            fields={
                'request_type': serializers.CharField(help_text='Тип запроса: 0x7a или 0x70'),
                'post_number': serializers.IntegerField(help_text='Номер поста наполнения'),
                'nfc_tag': serializers.CharField(required=False, help_text='NFC метка баллона'),
                'serial_number': serializers.CharField(required=False, help_text='Серийный номер баллона'),
                'size': serializers.IntegerField(required=False, help_text='Объем баллона'),
                'netto': serializers.FloatField(required=False, help_text='Вес пустого баллона'),
                'brutto': serializers.FloatField(required=False, help_text='Вес наполненного баллона'),
                'full_weight': serializers.FloatField(required=False, help_text='Полный вес (для типа 0x70)')
            }
        ),
        responses={
            200: OpenApiTypes.OBJECT,
            201: CarouselSerializer,
            400: inline_serializer(
                name='ErrorResponse',
                fields={
                    'error': serializers.CharField()
                }
            ),
            404: inline_serializer(
                name='ErrorResponse',
                fields={
                    'error': serializers.CharField()
                }
            ),
            500: inline_serializer(
                name='ErrorResponse',
                fields={
                    'error': serializers.CharField()
                }
            )
        },
        examples=[
            OpenApiExample(
                'Запрос типа 0x7a',
                value={
                    'request_type': '0x7a',
                    'post_number': 1,
                    'nfc_tag': '1234567890ABCDEF',
                    'serial_number': 'B12345',
                    'size': 50,
                    'netto': 18.5,
                    'brutto': 40.2
                },
                request_only=True
            ),
            OpenApiExample(
                'Запрос типа 0x70',
                value={
                    'request_type': '0x70',
                    'post_number': 1,
                    'full_weight': 40200.0
                },
                request_only=True
            )
        ]
    )
)
class CarouselViewSet(viewsets.ViewSet):
    permission_classes = [AllowAny]

    @action(detail=False, methods=['get'], url_path='get-parameter')
    def get_parameter(self, request):
        settings = CarouselSettings.objects.get(id=1)
        serializer = CarouselSettingsSerializer(settings)
        return Response(serializer.data)

    def partial_update(self, request, pk=1):
        """
        Запись параметров карусели
        :param request:
        :param pk: номер карусели
        :return:
        """
        carousel = get_object_or_404(CarouselSettings, id=pk)

        serializer = CarouselSettingsSerializer(carousel, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'], url_path='balloon-update')
    def update_from_carousel(self, request):
        request_type = request.data.get('request_type')
        post_number = request.data.get('post_number')

        logger.debug(f"Обработка запроса от карусели: Тип - {request_type}, пост - {post_number}")

        if not request_type:
            logger.error("Тип запроса отсутствует в теле запроса")
            return Response(
                {"error": "Не указан тип запроса"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            carousel_post = process_carousel_data(request.data)
            logger.debug(f"Данные по запросу {request_type} успешно сохранены")
            if request_type == '0x7a':
                return Response(
                    CarouselSerializer(carousel_post).data,
                    status=status.HTTP_201_CREATED,
                )
            return Response(status=status.HTTP_200_OK)
        except DjangoValidationError as error:
            logger.error(f"Ошибка валидации данных: {error}")
            error_data = getattr(error, 'message_dict', None) or {
                'error': '; '.join(error.messages)
            }
            return Response(error_data, status=status.HTTP_400_BAD_REQUEST)
        except CarouselPostNotFoundError as error:
            logger.error(str(error))
            return Response(
                {"error": str(error)},
                status=status.HTTP_404_NOT_FOUND,
            )
        except UnsupportedCarouselRequestError as error:
            logger.warning(str(error))
            return Response(
                {"error": str(error)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as error:
            logger.exception(f'Ошибка при обработке запроса: {error}')
            return Response(
                {"error": "Внутренняя ошибка сервера"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
