from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView


class MobileTokenObtainPairView(TokenObtainPairView):
    permission_classes = [AllowAny]
    authentication_classes = []


class MobileTokenRefreshView(TokenRefreshView):
    permission_classes = [AllowAny]
    authentication_classes = []
