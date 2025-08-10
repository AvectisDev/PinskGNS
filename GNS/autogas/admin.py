from django.contrib import admin
from .models import AutoGasBatch, AutoGasBatchSettings


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
    list_filter = [
        'begin_date',
        'end_date',
        'is_active'
    ]
    search_fields = ['truck']


@admin.register(AutoGasBatchSettings)
class AutoGasBatchSettingsAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'weight_source'
    ]
