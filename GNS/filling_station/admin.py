from django.contrib import admin
from import_export import resources
from .models import (
    Balloon,
    Truck,
    TruckType,
    Trailer,
    TrailerType,
    BalloonsBatch,
    ReaderSettings,
    TotalReadersCounter,
    DailyReaderCounter,
)


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
    search_fields = [
        'nfc_tag',
        'serial_number',
        'size',
        'manufacturer'
    ]


@admin.register(ReaderSettings)
class ReaderSettingsAdmin(admin.ModelAdmin):
    list_display = [
        'number',
        'status',
        'ip',
        'port',
        'function',
        'need_cache'
    ]
    search_fields = [
        'number',
        'status',
        'function'
    ]


@admin.register(Truck)
class TruckAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'car_brand',
        'registration_number',
        'type',
        'capacity_cylinders',
        'max_weight_of_transported_cylinders',
        'max_mass_of_transported_gas',
        'max_gas_volume',
        'empty_weight',
        'full_weight',
        'is_on_station',
        'entry_at',
        'departure_at'
    ]
    search_fields = [
        'car_brand',
        'registration_number',
        'type__type',
        'is_on_station'
    ]


@admin.register(TruckType)
class TruckTypeAdmin(admin.ModelAdmin):
    list_display = ['id', 'type']


@admin.register(Trailer)
class TrailerAdmin(admin.ModelAdmin):
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
        'entry_at',
        'departure_at'
    ]
    search_fields = [
        'trailer_brand',
        'registration_number',
        'type__type',
        'is_on_station'
    ]


@admin.register(TrailerType)
class TrailerTypeAdmin(admin.ModelAdmin):
    list_display = ['id', 'type']


@admin.register(BalloonsBatch)
class BalloonsBatchAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'batch_type',
        'started_at',
        'completed_at',
        'truck',
        'trailer',
        'reader_number',
        'amount_of_rfid',
        'amount_of_sensor',
        'amount_of_ttn',
        'amount_of_5_liters',
        'amount_of_12_liters',
        'amount_of_27_liters',
        'amount_of_50_liters',
        'gas_amount',
        'is_active',
        'miriada_close_failed',
        'display_ttn_name',
        'balloons_type',
    ]
    list_filter = ['batch_type', 'started_at', 'completed_at', 'is_active', 'miriada_close_failed']
    search_fields = ['truck', 'is_active', 'ttn_id', 'batch_type']

    @admin.display(description='Номер ТТН')
    def display_ttn_name(self, obj):
        return obj.get_ttn_name() or '—'


@admin.register(TotalReadersCounter)
class TotalsReaderCounterAdmin(admin.ModelAdmin):
    list_display = ['total_empty', 'total_full', 'changed_at']

    def has_add_permission(self, request):
        return not TotalReadersCounter.objects.exists()


@admin.register(DailyReaderCounter)
class DailyReaderCounterAdmin(admin.ModelAdmin):
    list_display = ['number', 'day', 'amount_of_rfid', 'amount_of_sensor', 'change_at']
    list_filter = ['number', 'day', 'change_at']
