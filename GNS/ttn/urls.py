from django.urls import path
from . import views

app_name = 'ttn'

urlpatterns = [
    # ТТН для баллонов
    path('balloons/', views.TTNView.as_view(), name="ttn_list"),
    path('balloons/create/', views.TTNCreateView.as_view(extra_context={
        "title": "Создание ТТН на приёмку/отгрузку баллонов"
    }),
         name="ttn_create"),
    path('balloons/<pk>/', views.TTNDetailView.as_view(), name="ttn_detail"),
    path('balloons/<pk>/update/', views.TTNUpdateView.as_view(extra_context={
        "title": "Редактирование ТТН на приёмку/отгрузку баллонов"
    }),
         name="ttn_update"),
    path('balloons/<pk>/delete/', views.TTNDeleteView.as_view(), name="ttn_delete"),

    # ТТН для ж/д цистерн
    path('railway/', views.RailwayTtnView.as_view(), name="railway_ttn_list"),
    path('railway/create/', views.RailwayTtnCreateView.as_view(extra_context={
        "title": "Создание ж/д ТТН"
    }),
         name="railway_ttn_create"),
    path('railway/<pk>/', views.RailwayTtnDetailView.as_view(), name="railway_ttn_detail"),
    path('railway/<pk>/update/', views.RailwayTtnUpdateView.as_view(extra_context={
        "title": "Редактирование ж/д ТТН"
    }),
         name="railway_ttn_update"),
    path('railway/<pk>/delete/', views.RailwayTtnDeleteView.as_view(), name="railway_ttn_delete"),

    # ТТН для авто цистерн
    path('auto/', views.AutoTtnView.as_view(), name="auto_ttn_list"),
    path('auto/create/', views.AutoTtnCreateView.as_view(extra_context={
        "title": "Создание ТТН на приёмку/отгрузку автоцистерн"
    }),
         name="auto_ttn_create"),
    path('auto/<pk>/', views.AutoTtnDetailView.as_view(), name="auto_ttn_detail"),
    path('auto/<pk>/update/', views.AutoTtnUpdateView.as_view(extra_context={
        "title": "Редактирование ТТН на приёмку/отгрузку автоцистерн"
    }),
         name="auto_ttn_update"),
    path('auto/<pk>/delete/', views.AutoTtnDeleteView.as_view(), name="auto_ttn_delete"),

    # Установка параметра источника веса для ТТН
    path('auto/update-weight-source/', views.update_weight_source, name="update_weight_source"),

]
