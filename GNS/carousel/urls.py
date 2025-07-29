from django.urls import path
from . import views

app_name = 'carousel'

urlpatterns = [
    path('<int:carousel_number>/', views.carousel_info, name='carousel_info'),
    path('settings/', views.CarouselSettingsDetailView.as_view(), name='carousel_settings_detail'),
    path('settings/update/', views.CarouselSettingsUpdateView.as_view(extra_context={
        "title": "Редактирование настроек карусели наполнения баллонов"
    }),
         name='carousel_settings_update'),
    ]
