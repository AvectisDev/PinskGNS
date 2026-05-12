from django.urls import path, include
from .views import check_connection

app_name = 'core'

urlpatterns = [
    path('', check_connection),
]
