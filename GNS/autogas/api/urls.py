from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import AutoGasBatchView

app_name = 'autogas'

# statistic
auto_gas_router = DefaultRouter()
auto_gas_router.register(r'', AutoGasBatchView, basename='auto-gas-batch')

urlpatterns = [
    path('', include(auto_gas_router.urls))
]
