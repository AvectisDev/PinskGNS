from django.urls import path
from . import views

app_name = 'autogas'

urlpatterns = [
    # Партии автоцистерн
    path('batch/', views.AutoGasBatchListView.as_view(), name="auto_gas_batch_list"),
    path('batch/<pk>/', views.AutoGasBatchDetailView.as_view(), name="auto_gas_batch_detail"),
    path('batch/<pk>/update/', views.AutoGasBatchUpdateView.as_view(extra_context={
        "title": "Редактирование партии приёмки/отгрузки газа в автоцистернах"
    }),
         name="auto_gas_batch_update"),
    path('batch/<pk>/delete/', views.AutoGasBatchDeleteView.as_view(), name="auto_gas_batch_delete"),
]
