from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import balloons, transport
from rest_framework_simplejwt.views import (TokenObtainPairView, TokenRefreshView)


app_name = 'filling_station'

balloons_loading_router = DefaultRouter()
balloons_loading_router.register(r'balloons-loading',
                                 balloons.BalloonsLoadingBatchViewSet,
                                 basename='balloons-loading')

balloons_unloading_router = DefaultRouter()
balloons_unloading_router.register(r'balloons-unloading',
                                   balloons.BalloonsUnloadingBatchViewSet,
                                   basename='balloons-unloading')

balloons_router = DefaultRouter()
balloons_router.register(r'balloons', balloons.BalloonViewSet, basename='balloons')

balloons_amount_router = DefaultRouter()
balloons_amount_router.register(r'balloons-amount', balloons.BalloonAmountViewSet, basename='balloonamount')

urlpatterns = [
    path('', include(balloons_router.urls)),
    path('balloon-status-options', balloons.get_balloon_status_options),
    path('loading-balloon-reader-list', balloons.get_loading_balloon_reader_list),
    path('unloading-balloon-reader-list', balloons.get_unloading_balloon_reader_list),

    path('trucks', transport.TruckView.as_view()),
    path('trailers', transport.TrailerView.as_view()),
    path('railway-tanks', transport.RailwayTanksView.as_view()),

    path('', include(balloons_loading_router.urls)),
    path('', include(balloons_unloading_router.urls)),

    path('', include(balloons_amount_router.urls)),

    path('railway-loading', transport.RailwayBatchView.as_view()),
    path('auto-gas', transport.AutoGasBatchView.as_view()),

    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]
