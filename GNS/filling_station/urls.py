from django.urls import path
from . import views

app_name = 'filling_station'

urlpatterns = [
    # Архив баллонов
    path('', views.BalloonListView.as_view(), name='balloon_list'),
    path('balloon/<pk>/', views.BalloonDetailView.as_view(), name='balloon_detail'),
    path("balloon/<pk>/update/", views.BalloonUpdateView.as_view(extra_context={
        "title": "Редактирование паспорта баллона"
    }),
         name="balloon_update"),
    path("balloon/<pk>/delete/", views.BalloonDeleteView.as_view(), name="balloon_delete"),

    # Таблицы считывателей
    path('reader/<int:reader>', views.reader_info, name="reader"),

    # Партии приёмки баллонов
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

    # Партии отгрузки баллонов
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

    # Партии автоцистерн
    path('batch/auto-gas', views.AutoGasBatchListView.as_view(), name="auto_gas_batch_list"),
    path('batch/auto-gas/<pk>/', views.AutoGasBatchDetailView.as_view(), name="auto_gas_batch_detail"),
    path('batch/auto-gas/<pk>/update/', views.AutoGasBatchUpdateView.as_view(extra_context={
        "title": "Редактирование партии приёмки/отгрузки газа в автоцистернах"
    }),
         name="auto_gas_batch_update"),
    path('batch/auto-gas/<pk>/delete/', views.AutoGasBatchDeleteView.as_view(), name="auto_gas_batch_delete"),

    # Грузовики
    path('transport/trucks', views.TruckView.as_view(), name="truck_list"),
    path('transport/trucks/create', views.TruckCreateView.as_view(extra_context={
        "title": "Создание грузовика"
    }),
         name="truck_create"),
    path('transport/trucks/<pk>', views.TruckDetailView.as_view(), name="truck_detail"),
    path('transport/trucks/<pk>/update/',
         views.TruckUpdateView.as_view(extra_context={
             "title": "Редактирование грузовика"
         }),
         name="truck_update"),
    path('transport/trucks/<pk>/delete/', views.TruckDeleteView.as_view(), name="truck_delete"),

    # Прицепы
    path('transport/trailers', views.TrailerView.as_view(), name="trailer_list"),
    path('transport/trailers/create', views.TrailerCreateView.as_view(extra_context={
        "title": "Создание прицепа"
    }),
         name="trailer_create"),
    path('transport/trailers/<pk>', views.TrailerDetailView.as_view(), name="trailer_detail"),
    path('transport/trailers/<pk>/update/', views.TrailerUpdateView.as_view(extra_context={
        "title": "Редактирование прицепа"
    }),
         name="trailer_update"),
    path('transport/trailers/<pk>/delete/', views.TrailerDeleteView.as_view(), name="trailer_delete"),

    # Статистика
    path('statistic', views.statistic, name="statistic"),
]
