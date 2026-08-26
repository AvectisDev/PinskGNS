"""URL-маршруты REST API filling_station: баллоны, партии, транспорт и JWT для мобильного клиента."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import balloon_batches, balloons, transport
from .auth import MobileTokenObtainPairView, MobileTokenRefreshView

app_name = 'filling_station'

balloons_router = DefaultRouter()
balloons_router.register(r'balloons', balloons.BalloonViewSet, basename='balloons')
balloons_router.register(
    r'balloons-loading',
    balloon_batches.BalloonsBatchViewSet,
    basename='balloons-loading',
)
balloons_router.register(
    r'balloons-unloading',
    balloon_batches.BalloonsBatchViewSet,
    basename='balloons-unloading',
)


urlpatterns = [
    path('', include(balloons_router.urls)),
    path('balloon-status-options', balloons.get_balloon_status_options),
    path('loading-balloon-reader-list', balloons.get_loading_balloon_reader_list),
    path('unloading-balloon-reader-list', balloons.get_unloading_balloon_reader_list),
    path('get-active-balloon-batch', balloon_batches.get_active_balloon_batch),
    path('total-readers-counter/manual-values', balloons.set_total_readers_counter_manual_values),

    path('trucks', transport.TruckView.as_view()),
    path('trailers', transport.TrailerView.as_view()),

    path('token/', MobileTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', MobileTokenRefreshView.as_view(), name='token_refresh'),
]
