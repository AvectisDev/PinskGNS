from django.contrib import admin
from .models import AutoGasBatch, AutoGasBatchSettings


@admin.register(AutoGasBatch)
class AutoGasBatchAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'batch_type',
        'completed_at',
        'truck',
        'trailer',
        'gas_amount',
        'gas_type',
        'scale_empty_weight',
        'scale_full_weight',
        'weight_gas_amount',
        'is_active',
    ]
    list_filter = [
        'begin_at',
        'completed_at',
        'is_active',
    ]
    search_fields = ['truck', 'trailer']

@admin.register(AutoGasBatchSettings)
class AutoGasBatchSettingsAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'weight_source'
    ]
