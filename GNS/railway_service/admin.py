from django.contrib import admin
from .models import RailwayTank, RailwayBatch


@admin.register(RailwayTank)
class RailwayTankAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'registration_number',
        'empty_weight',
        'full_weight',
        'gas_weight',
        'gas_type',
        'is_on_station',
        'railway_ttn',
        'netto_weight_ttn',
        'entry_date',
        'entry_time',
        'departure_date',
        'departure_time',
        'registration_number_img'
    ]
    search_fields = ['registration_number', 'is_on_station', 'entry_date', 'departure_date']
    list_filter = ['entry_date', 'departure_date', 'is_on_station']


@admin.register(RailwayBatch)
class RailwayBatchAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'begin_date',
        'end_date',
        'gas_amount_spbt',
        'gas_amount_pba',
        'is_active'
    ]
    list_filter = ['begin_date', 'end_date', 'is_active']
