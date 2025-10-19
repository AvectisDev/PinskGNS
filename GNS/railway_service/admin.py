from django.contrib import admin
from .models import RailwayTank, RailwayBatch, RailwayTankHistory


class RailwayTankHistoryInline(admin.TabularInline):
    model = RailwayTankHistory
    extra = 0
    fields = (
        'arrival_at',
        'departure_at',
        'full_weight',
        'empty_weight',
        'gas_weight',
        'railway_ttn',
        'netto_weight_ttn',
    )
    readonly_fields = ()


@admin.register(RailwayTank)
class RailwayTankAdmin(admin.ModelAdmin):
    list_display = [
        'registration_number',
        'gas_type',
        'is_on_station',
        ]
    search_fields = ['registration_number']
    list_filter = ['is_on_station']
    inlines = [RailwayTankHistoryInline]


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
