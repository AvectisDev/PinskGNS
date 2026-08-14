from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny


@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def check_connection(request):
    return Response(status=status.HTTP_200_OK)
