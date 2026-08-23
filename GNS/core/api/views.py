from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from drf_spectacular.utils import extend_schema, inline_serializer


CheckConnectionResponseSerializer = inline_serializer(
    name='CheckConnectionResponse',
    fields={
        'status': serializers.CharField(help_text='Статус доступности API'),
    },
)


@extend_schema(
    tags=['Health'],
    summary='Проверка доступности API',
    description='Публичный health-check. Не требует аутентификации.',
    responses={200: CheckConnectionResponseSerializer},
)
@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def check_connection(request):
    return Response({'status': 'ok'}, status=status.HTTP_200_OK)
