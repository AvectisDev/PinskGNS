import base64
import os

from django.http import FileResponse
from drf_spectacular.utils import OpenApiExample, extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from ..models import MobileApp
from .serializers import MobileAppSerializer


@extend_schema(
    tags=['Мобильное приложение'],
    summary='Актуальная версия приложения',
    description='Метаданные последней версии мобильного приложения.',
    responses={
        200: MobileAppSerializer,
        404: inline_serializer(
            name='MobileAppNotFound',
            fields={'error': serializers.CharField()},
        ),
    },
)
@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def get_app_version(request):
    latest_app = MobileApp.objects.order_by('-update_date').first()
    if not latest_app:
        return Response({"error": "No app versions available"}, status=404)

    serializer = MobileAppSerializer(latest_app, context={'request': request})
    return Response(serializer.data)


@extend_schema(
    tags=['Мобильное приложение'],
    summary='Скачать APK (base64)',
    description='Последний APK в виде base64 и имя файла.',
    responses={
        200: inline_serializer(
            name='MobileApkPayload',
            fields={
                'ApkBytes': serializers.CharField(),
                'FileName': serializers.CharField(),
                'Version': serializers.CharField(),
            },
        ),
        404: inline_serializer(
            name='MobileApkNotFound',
            fields={'error': serializers.CharField()},
        ),
        500: inline_serializer(
            name='MobileApkError',
            fields={'error': serializers.CharField()},
        ),
    },
    examples=[
        OpenApiExample(
            'Успех',
            value={
                'ApkBytes': 'UEsDBBQAAAA...',
                'FileName': 'Lida_app_1.0.0.apk',
                'Version': '1.0.0',
            },
            response_only=True,
        ),
    ],
)
@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def get_app_apk(request):
    latest_app = MobileApp.objects.order_by('-update_date').first()
    if not latest_app:
        return Response({"error": "No APK file available"}, status=404)

    try:
        file_path = latest_app.apk_file.path
        apk_file_name = f"Lida_app_{latest_app.version_name}.apk"

        if not os.path.exists(file_path):
            return Response({"error": "APK file not found on server"}, status=404)

        with open(file_path, 'rb') as apk_file:
            apk_bytes = apk_file.read()
            apk_base64 = base64.b64encode(apk_bytes).decode('utf-8')

        response_data = {
            'ApkBytes': apk_base64,
            'FileName': apk_file_name,
            'Version': latest_app.version_name
        }
        return Response(response_data)

    except Exception as e:
        return Response({"error": str(e)}, status=500)
