from django.urls import path
from .api import views


app_name = 'mobile'

urlpatterns = [
    path('app/version/', views.get_app_version),
    path('app/apk/', views.get_app_apk)
]
