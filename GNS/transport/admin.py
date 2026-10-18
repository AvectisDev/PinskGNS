"""Регистрация моделей транспорта в Django Admin."""

from django import forms
from django.contrib import admin

from transport.form_choices import configure_driver_field
from transport.models import Driver, Trailer, TrailerType, Truck, TruckType
from transport.registration import (
    TRAILER_INPUT_HELP,
    TRUCK_INPUT_HELP,
    validate_trailer_input,
    validate_truck_input,
)


class TruckAdminForm(forms.ModelForm):
    """Admin-форма грузовика со строгой валидацией номера."""

    class Meta:
        model = Truck
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['registration_number'].help_text = TRUCK_INPUT_HELP
        configure_driver_field(self.fields['driver'], truck=self.instance)

    def clean_registration_number(self):
        return validate_truck_input(self.cleaned_data.get('registration_number', ''))


class TrailerAdminForm(forms.ModelForm):
    """Admin-форма прицепа со строгой валидацией номера."""

    class Meta:
        model = Trailer
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['registration_number'].help_text = TRAILER_INPUT_HELP

    def clean_registration_number(self):
        return validate_trailer_input(self.cleaned_data.get('registration_number', ''))


@admin.register(Driver)
class DriverAdmin(admin.ModelAdmin):
    """Админка справочника водителей."""

    list_display = ['id', 'full_name', 'comment', 'is_active']
    list_filter = ['is_active']
    search_fields = ['full_name', 'comment']


@admin.register(Truck)
class TruckAdmin(admin.ModelAdmin):
    """Админка грузовиков."""

    form = TruckAdminForm
    list_display = [
        'id',
        'car_brand',
        'registration_number',
        'type',
        'driver',
        'capacity_cylinders',
        'max_weight_of_transported_cylinders',
        'max_mass_of_transported_gas',
        'max_gas_volume',
        'empty_weight',
        'full_weight',
        'is_on_station',
        'is_active',
        'entry_at',
        'departure_at',
    ]
    list_filter = ['is_on_station', 'is_active', 'type', 'driver']
    search_fields = [
        'car_brand',
        'registration_number',
        'type__type',
        'driver__full_name',
    ]


@admin.register(TruckType)
class TruckTypeAdmin(admin.ModelAdmin):
    """Админка справочника типов грузовиков."""

    list_display = ['id', 'type']


@admin.register(Trailer)
class TrailerAdmin(admin.ModelAdmin):
    """Админка прицепов."""

    form = TrailerAdminForm
    list_display = [
        'id',
        'truck',
        'trailer_brand',
        'registration_number',
        'type',
        'capacity_cylinders',
        'max_weight_of_transported_cylinders',
        'max_mass_of_transported_gas',
        'max_gas_volume',
        'empty_weight',
        'full_weight',
        'is_on_station',
        'is_active',
        'entry_at',
        'departure_at',
    ]
    list_filter = ['is_on_station', 'is_active', 'type']
    search_fields = [
        'trailer_brand',
        'registration_number',
        'type__type',
    ]


@admin.register(TrailerType)
class TrailerTypeAdmin(admin.ModelAdmin):
    """Админка справочника типов прицепов."""

    list_display = ['id', 'type']
