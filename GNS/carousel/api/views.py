from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from drf_spectacular.utils import (
    extend_schema,
    extend_schema_view,
    OpenApiTypes,
    OpenApiParameter,
)
from carousel.models import CarouselSettings
from .serializers import CarouselSettingsSerializer
from core.api.schema import ApiErrorSerializer


@extend_schema_view(
    get_parameter=extend_schema(
        tags=['Карусель'],
        summary='Получить параметры карусели',
        description='Получение настроек карусели наполнения баллонов',
        responses={
            200: CarouselSettingsSerializer,
            404: ApiErrorSerializer
        }
    ),
    partial_update=extend_schema(
        tags=['Карусель'],
        summary='Обновить параметры карусели',
        description='Частичное обновление настроек карусели',
        request=CarouselSettingsSerializer,
        responses={
            200: CarouselSettingsSerializer,
            400: ApiErrorSerializer,
            404: ApiErrorSerializer
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
