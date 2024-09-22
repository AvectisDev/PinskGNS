from django.urls import path
from . import views

app_name = 'filling_station'

urlpatterns = [
    path('', views.BalloonListView.as_view(), name='balloon_list'),
    path('balloon/<pk>/', views.BalloonDetailView.as_view(), name='balloon_detail'),
    path("balloon/<pk>/update/", views.BalloonUpdateView.as_view(extra_context={
        "title": "Редактирование паспорта баллона"
    }),
         name="balloon_update"),
    path("balloon/<pk>/delete/", views.BalloonDeleteView.as_view(), name="balloon_delete"),

    path('reader/<str:reader>', views.reader_info, name="reader"),

    path('batch/balloons-loading', views.BalloonLoadingBatchListView.as_view(extra_context={
        "title": "Партии приёмки баллонов"
    }),
         name="balloon_loading_batch_list"),
    path('batch/balloons-loading/<pk>/', views.BalloonLoadingBatchDetailView.as_view(extra_context={
        "title": "Детали партии приёмки баллонов",
        "main_list": "loading"
    }),
         name="balloon_loading_batch_detail"),
    path('batch/balloons-loading/<pk>/update/', views.BalloonLoadingBatchUpdateView.as_view(extra_context={
        "title": "Редактирование партии приёмки баллонов"
    }),
         name="balloon_loading_batch_update"),
    path('batch/balloons-loading/<pk>/delete/', views.BalloonLoadingBatchDeleteView.as_view(),
         name="balloon_loading_batch_delete"),

    path('batch/balloons-unloading', views.BalloonUnloadingBatchListView.as_view(extra_context={
        "title": "Партии отгрузки баллонов"
    }),
         name="balloon_unloading_batch_list"),
    path('batch/balloons-unloading/<pk>/', views.BalloonUnloadingBatchDetailView.as_view(extra_context={
        "title": "Детали партии отгрузки баллонов",
        "main_list": "unloading"
    }),
         name="balloon_unloading_batch_detail"),
    path('batch/balloons-unloading/<pk>/update/', views.BalloonUnloadingBatchUpdateView.as_view(extra_context={
        "title": "Редактирование партии отгрузки баллонов"
    }),
         name="balloon_unloading_batch_update"),
    path('batch/balloons-unloading/<pk>/delete/', views.BalloonUnloadingBatchDeleteView.as_view(),
         name="balloon_unloading_batch_delete"),

    path('batch/railway-loading', views.RailwayLoadingBatchListView.as_view(),
         name="railway_loading_batch_list"),
    path('batch/railway-loading/<pk>/', views.RailwayLoadingBatchDetailView.as_view(),
         name="railway_loading_batch_detail"),
    path('batch/railway-loading/<pk>/update/', views.RailwayLoadingBatchUpdateView.as_view(extra_context={
        "title": "Редактирование партии приёмки газа в цистернах"
    }),
         name="railway_loading_batch_update"),
    path('batch/railway-loading/<pk>/delete/', views.RailwayLoadingBatchDeleteView.as_view(),
         name="railway_loading_batch_delete"),

    path('batch/auto-gas-loading', views.GasLoadingBatchListView.as_view(extra_context={
        "title": "Партии приёмки газа в авто-цистернах"
    }),
         name="gas_loading_batch_list"),
    path('batch/auto-gas-loading/<pk>/', views.GasLoadingBatchDetailView.as_view(extra_context={
        "main_list": "loading"
    }),
         name="gas_loading_batch_detail"),
    path('batch/auto-gas-loading/<pk>/update/', views.GasLoadingBatchUpdateView.as_view(extra_context={
        "title": "Редактирование партии приёмки газа в авто-цистернах"
    }),
         name="gas_loading_batch_update"),
    path('batch/auto-gas-loading/<pk>/delete/', views.GasLoadingBatchDeleteView.as_view(),
         name="gas_loading_batch_delete"),

    path('batch/auto-gas-unloading', views.GasUnloadingBatchListView.as_view(extra_context={
        "title": "Партии отгрузки газа в авто-цистернах"
    }),
         name="gas_unloading_batch_list"),
    path('batch/auto-gas-unloading/<pk>/', views.GasUnloadingBatchDetailView.as_view(extra_context={
        "main_list": "unloading"
    }),
         name="gas_unloading_batch_detail"),
    path('batch/auto-gas-unloading/<pk>/update/', views.GasUnloadingBatchUpdateView.as_view(extra_context={
        "title": "Редактирование партии отгрузки газа в авто-цистернах"
    }),
         name="gas_unloading_batch_update"),
    path('batch/auto-gas-unloading/<pk>/delete/', views.GasUnloadingBatchDeleteView.as_view(),
         name="gas_unloading_batch_delete"),

    path('ttn', views.TTNView.as_view(), name="ttn_list"),
    path('ttn/<pk>', views.TTNDetailView.as_view(), name="ttn_detail"),
    path('ttn/<pk>/update/', views.TTNUpdateView.as_view(extra_context={
        "title": "Редактирование ТТН"
    }),
         name="ttn_update"),
    path('ttn/<pk>/delete/', views.TTNDeleteView.as_view(), name="ttn_delete"),

    path('transport/trucks', views.TruckView.as_view(), name="truck_list"),
    path('transport/trucks/<pk>', views.TruckDetailView.as_view(), name="truck_detail"),
    path('transport/trucks/<pk>/update/',
         views.TruckUpdateView.as_view(extra_context={
             "title": "Редактирование грузовика"
         }),
         name="truck_update"),
    path('transport/trucks/<pk>/delete/', views.TruckDeleteView.as_view(), name="truck_delete"),

    path('transport/trailers', views.TrailerView.as_view(), name="trailer_list"),
    path('transport/trailers/<pk>', views.TrailerDetailView.as_view(), name="trailer_detail"),
    path('transport/trailers/<pk>/update/', views.TrailerUpdateView.as_view(extra_context={
        "title": "Редактирование прицепа"
    }),
         name="trailer_update"),
    path('transport/trailers/<pk>/delete/', views.TrailerDeleteView.as_view(), name="trailer_delete"),

    path('transport/railway_tanks', views.RailwayTankView.as_view(), name="railway_tank_list"),
    path('transport/railway_tanks/<pk>', views.RailwayTankDetailView.as_view(), name="railway_tank_detail"),
    path('transport/railway_tanks/<pk>/update/', views.RailwayTankUpdateView.as_view(extra_context={
        "title": "Редактирование ж/д цистерны"
    }),
         name="railway_tank_update"),
    path('transport/railway_tanks/<pk>/delete/', views.RailwayTankDeleteView.as_view(), name="railway_tank_delete"),
]
