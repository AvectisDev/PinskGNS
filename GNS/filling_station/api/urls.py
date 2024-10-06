from django.urls import path
from . import api
from rest_framework_simplejwt.views import (TokenObtainPairView, TokenRefreshView)
from django.views.decorators.csrf import csrf_exempt


app_name = 'filling_station'

urlpatterns = [
    path('balloon-passport', api.BalloonView.as_view()),
    path('balloon-status-options', api.get_balloon_status_options),
    path('loading-balloon-reader-list', api.get_loading_balloon_reader_list),
    path('unloading-balloon-reader-list', api.get_unloading_balloon_reader_list),

    path('trucks', api.TruckView.as_view()),
    path('trailers', api.TrailerView.as_view()),
    path('railway-tanks', api.RailwayTanksView.as_view()),

    path('balloons-loading', api.BalloonsLoadingBatchView.as_view()),
    path('balloons-loading/add-balloon', api.add_balloon_to_loading_batch),
    path('balloons-loading/remove-balloon', api.remove_balloon_from_loading_batch),

    path('balloons-unloading', api.BalloonsUnloadingBatchView.as_view()),
    path('balloons-unloading/add-balloon', api.add_balloon_to_unloading_batch),
    path('balloons-unloading/remove-balloon', api.remove_balloon_from_unloading_batch),

    path('railway-loading', api.RailwayBatchView.as_view()),
    path('auto-gas', api.AutoGasBatchView.as_view()),

    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]
