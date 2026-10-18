"""URL-маршруты REST API транспорта."""

from django.urls import path

from transport.api import views

urlpatterns = [
    path('trucks', views.TruckView.as_view()),
    path('trailers', views.TrailerView.as_view()),
]
