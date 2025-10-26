from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import balloons, transport
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

app_name = 'filling_station'

balloons_router = DefaultRouter()
balloons_router.register(r'balloons', balloons.BalloonViewSet, basename='balloons')
balloons_router.register(r'balloons-loading', balloons.BalloonsBatchViewSet, basename='balloons-loading')
balloons_router.register(r'balloons-unloading', balloons.BalloonsBatchViewSet, basename='balloons-unloading')


urlpatterns = [
    path('', include(balloons_router.urls)),
    path('balloon-status-options', balloons.get_balloon_status_options),
    path('loading-balloon-reader-list', balloons.get_loading_balloon_reader_list),
    path('unloading-balloon-reader-list', balloons.get_unloading_balloon_reader_list),
    path('get-active-balloon-batch', balloons.get_active_balloon_batch),

    path('trucks', transport.TruckView.as_view()),
    path('trailers', transport.TrailerView.as_view()),

    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]
