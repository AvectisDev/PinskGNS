from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'carousel'

carousel_router = DefaultRouter()
carousel_router.register(r'carousel', views.CarouselViewSet, basename='carousel')

urlpatterns = [
    path('', include(carousel_router.urls)),
    ]
