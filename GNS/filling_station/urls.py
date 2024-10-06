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

    path('batch/railway', views.RailwayBatchListView.as_view(), name="railway_batch_list"),
    path('batch/railway/<pk>/', views.RailwayBatchDetailView.as_view(), name="railway_batch_detail"),
    path('batch/railway/<pk>/update/', views.RailwayBatchUpdateView.as_view(extra_context={
        "title": "Редактирование партии приёмки газа в цистернах"
    }),
         name="railway_batch_update"),
    path('batch/railway/<pk>/delete/', views.RailwayBatchDeleteView.as_view(), name="railway_batch_delete"),

    path('batch/auto-gas', views.AutoGasBatchListView.as_view(), name="auto_gas_batch_list"),
    path('batch/auto-gas/<pk>/', views.AutoGasBatchDetailView.as_view(), name="auto_gas_batch_detail"),
    path('batch/auto-gas/<pk>/update/', views.AutoGasBatchUpdateView.as_view(), name="auto_gas_batch_update"),
    path('batch/auto-gas/<pk>/delete/', views.AutoGasBatchDeleteView.as_view(), name="auto_gas_batch_delete"),

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
