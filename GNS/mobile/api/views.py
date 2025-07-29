import base64
import os
from ..models import MobileApp
from rest_framework.response import Response
from rest_framework.decorators import api_view, action, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from .serializers import MobileAppSerializer
from django.http import FileResponse


@api_view(['GET'])
@permission_classes([AllowAny])
def get_app_version(request):
    latest_app = MobileApp.objects.order_by('-update_date').first()
    if not latest_app:
        return Response({"error": "No app versions available"}, status=404)

    serializer = MobileAppSerializer(latest_app, context={'request': request})
    return Response(serializer.data)


@api_view(['GET'])
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