from django.urls import path
from .api import views


app_name = 'mobile'

urlpatterns = [
    path('version/', views.get_app_version),
    path('apk/', views.get_app_apk)
]
