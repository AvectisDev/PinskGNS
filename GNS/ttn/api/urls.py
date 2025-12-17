from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import MiriadaTtnViewSet

app_name = 'ttn_api'

ttn_router = DefaultRouter()
ttn_router.register(r'miriada', MiriadaTtnViewSet, basename='miriada-ttn')

urlpatterns = [
    path('', include(ttn_router.urls)),
]

