"""JWT-эндпоинты мобильного API без обязательной предварительной аутентификации."""

from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView


class MobileTokenObtainPairView(TokenObtainPairView):
    """Выдача пары access/refresh JWT для мобильного клиента."""

    permission_classes = [AllowAny]
    authentication_classes = []


class MobileTokenRefreshView(TokenRefreshView):
    """Обновление access-токена по refresh JWT для мобильного клиента."""

    permission_classes = [AllowAny]
    authentication_classes = []
