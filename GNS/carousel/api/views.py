from django.conf import settings
from django.shortcuts import get_object_or_404
from rest_framework import generics, status, viewsets
from rest_framework.response import Response
from rest_framework.decorators import api_view, action
from rest_framework.permissions import IsAuthenticated, AllowAny
import logging
from ..models import Carousel, CarouselSettings
from .serializers import CarouselSerializer, CarouselSettingsSerializer


logger = logging.getLogger('carousel')


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
        """

        """
        request_type = request.data.get('request_type')
        post_number = request.data.get('post_number')

        logger.debug(f"Обработка запроса от карусели: Тип - {request_type}, пост - {post_number}")
        if not request_type:
            logger.error("Тип запроса отсутствует в теле запроса")
            return Response({"error": "Не указан тип запроса"}, status=status.HTTP_400_BAD_REQUEST)

        if request_type == '0x7a':
            # Валидируем и сохраняем данные через сериализатор
            serializer = CarouselSerializer(data=request.data)
            if serializer.is_valid():
                serializer.save()
                logger.debug(f"Данные по запросу 0x7a успешно сохранены")
                return Response(serializer.data, status=status.HTTP_201_CREATED)
        else:
            try:
                carousel_post = Carousel.objects.filter(post_number=post_number).first()
                carousel_post.is_empty = False
                carousel_post.full_weight = request.data.get('full_weight')
                carousel_post.save()
                logger.debug(f"Данные по запросу 0x70 успешно сохранены")
                return Response(status=status.HTTP_200_OK)
            except Exception as error:
                logger.error(f'Ошибка при обработке запроса типа 0x70 - {error}')
                return Response({"error": str(error)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)