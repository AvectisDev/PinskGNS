from django.contrib import admin
from .models import (Balloon, Truck, TruckType, Trailer, TrailerType, BalloonsLoadingBatch, BalloonsUnloadingBatch,
                     AutoGasBatch, AutoGasBatchSettings)
from import_export import resources


class BalloonResources(resources.ModelResource):
    class Meta:
        model = Balloon
        fields = [
            'nfc_tag',
            'serial_number',
            'size',
            'netto',
            'brutto',
            'filling_status',
            "change_date"
        ]


@admin.register(Balloon)
class BalloonAdmin(admin.ModelAdmin):
    list_display = [
        'nfc_tag',
        'serial_number',
        'creation_date',
        'size',
        'netto',
        'brutto',
        'current_examination_date',
        'next_examination_date',
        'diagnostic_date',
        'working_pressure',
        'status',
        'manufacturer',
        'wall_thickness',
        'filling_status',
        'update_passport_required'
    ]
    search_fields = ['nfc_tag', 'serial_number', 'size', 'manufacturer']


@admin.register(Truck)
class TruckAdmin(admin.ModelAdmin):
    list_display = ['id', 'car_brand', 'registration_number', 'type', 'capacity_cylinders',
                    'max_weight_of_transported_cylinders', 'max_mass_of_transported_gas', 'max_gas_volume',
                    'empty_weight', 'full_weight', 'is_on_station', 'entry_date', 'entry_time', 'departure_date',
                    'departure_time']
    search_fields = ['car_brand', 'registration_number', 'type', 'is_on_station', 'entry_date', 'departure_date']


@admin.register(TruckType)
class TruckTypeAdmin(admin.ModelAdmin):
    list_display = ['id', 'type']


@admin.register(Trailer)
class TrailerAdmin(admin.ModelAdmin):
    list_display = ['id', 'truck', 'trailer_brand', 'registration_number', 'type', 'capacity_cylinders',
                    'max_weight_of_transported_cylinders', 'max_mass_of_transported_gas', 'max_gas_volume', 'empty_weight',
                    'full_weight', 'is_on_station', 'entry_date', 'entry_time', 'departure_date', 'departure_time']
    search_fields = ['trailer_brand', 'registration_number', 'type', 'is_on_station']


@admin.register(TrailerType)
class TrailerTypeAdmin(admin.ModelAdmin):
    list_display = ['id', 'type']


@admin.register(BalloonsLoadingBatch)
class BalloonsLoadingBatchAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'begin_date',
        'begin_time',
        'end_date',
        'end_time',
        'truck',
        'trailer',
        'reader_number',
        'amount_of_rfid',
        'amount_of_5_liters',
        'amount_of_12_liters',
        'amount_of_27_liters',
        'amount_of_50_liters',
        'gas_amount',
        'is_active',
        'ttn',
        'amount_of_ttn'
    ]
    list_filter = ['begin_date', 'end_date', 'is_active']
    search_fields = ['truck', 'is_active', 'ttn']


@admin.register(BalloonsUnloadingBatch)
class BalloonsUnloadingBatchAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'begin_date',
        'begin_time',
        'end_date',
        'end_time',
        'truck',
        'trailer',
        'reader_number',
        'amount_of_rfid',
        'amount_of_5_liters',
        'amount_of_12_liters',
        'amount_of_27_liters',
        'amount_of_50_liters',
        'gas_amount',
        'is_active',
        'ttn',
        'amount_of_ttn'
    ]
    list_filter = ['begin_date', 'end_date', 'is_active']
    search_fields = ['truck', 'ttn']


@admin.register(AutoGasBatch)
class AutoGasBatchAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'batch_type',
        'end_date',
        'end_time',
        'truck',
        'trailer',
        'gas_amount',
        'gas_type',
        'scale_empty_weight',
        'scale_full_weight',
        'weight_gas_amount',
        'is_active'
    ]
    list_filter = ['begin_date', 'end_date', 'is_active']
    search_fields = ['truck']


@admin.register(AutoGasBatchSettings)
class AutoGasBatchSettingsAdmin(admin.ModelAdmin):
    list_display = ['id', 'weight_source']
