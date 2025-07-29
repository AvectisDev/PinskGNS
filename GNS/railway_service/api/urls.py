from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .api_views import RailwayBatchView

app_name = 'railway_service'

# statistic
railway_batch_router = DefaultRouter()
railway_batch_router.register(r'', RailwayBatchView, basename='railway-batch')

urlpatterns = [
    path('', include(railway_batch_router.urls)),
]
