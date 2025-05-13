from django.urls import path
from . import views

app_name = 'railway_service'

urlpatterns = [
    # Ж/д цистерны
    path('transport/railway_tanks', views.RailwayTankView.as_view(), name="railway_tank_list"),
    path('transport/railway_tanks/create', views.RailwayTankCreateView.as_view(extra_context={
        "title": "Создание ж/д цистерны"
    }),
         name="railway_tank_create"),
    path('transport/railway_tanks/<pk>', views.RailwayTankDetailView.as_view(), name="railway_tank_detail"),
    path('transport/railway_tanks/<pk>/update/', views.RailwayTankUpdateView.as_view(extra_context={
        "title": "Редактирование ж/д цистерны"
    }),
         name="railway_tank_update"),
    path('transport/railway_tanks/<pk>/delete/', views.RailwayTankDeleteView.as_view(), name="railway_tank_delete"),

    # Партии ж/д цистерн
    path('batch/', views.RailwayBatchListView.as_view(), name="railway_batch_list"),
    path('batch/<pk>/', views.RailwayBatchDetailView.as_view(), name="railway_batch_detail"),
    path('batch/<pk>/update/', views.RailwayBatchUpdateView.as_view(extra_context={
        "title": "Редактирование партии приёмки газа в цистернах"
    }),
         name="railway_batch_update"),
    path('batch/<pk>/delete/', views.RailwayBatchDeleteView.as_view(), name="railway_batch_delete"),
]
