from django.urls import path

from transport import views

app_name = 'transport'

urlpatterns = [
    path('transport/trucks/', views.TruckView.as_view(), name='truck_list'),
    path('transport/trucks/create/', views.TruckCreateView.as_view(extra_context={
        'title': 'Создание грузовика'
    }), name='truck_create'),
    path('transport/trucks/<pk>/', views.TruckDetailView.as_view(), name='truck_detail'),
    path('transport/trucks/<pk>/update/', views.TruckUpdateView.as_view(extra_context={
        'title': 'Редактирование грузовика'
    }), name='truck_update'),
    path('transport/trucks/<pk>/delete/', views.TruckDeleteView.as_view(), name='truck_delete'),

    path('transport/trailers/', views.TrailerView.as_view(), name='trailer_list'),
    path('transport/trailers/create/', views.TrailerCreateView.as_view(extra_context={
        'title': 'Создание прицепа'
    }), name='trailer_create'),
    path('transport/trailers/<pk>/', views.TrailerDetailView.as_view(), name='trailer_detail'),
    path('transport/trailers/<pk>/update/', views.TrailerUpdateView.as_view(extra_context={
        'title': 'Редактирование прицепа'
    }), name='trailer_update'),
    path('transport/trailers/<pk>/delete/', views.TrailerDeleteView.as_view(), name='trailer_delete'),
]
