from django.contrib import admin
from .models import BalloonTtn, AutoTtn, RailwayTtn, Contractor, City, FilePath

@admin.register(BalloonTtn)
class TTNAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'number',
        'contract',
        'shipper',
        'consignee',
        'city',
        'date'
    ]
    search_fields = [
        'number',
        'contract',
        'consignee',
        'city'
    ]
    list_filter = ['date']


@admin.register(AutoTtn)
class AutoTtnAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'number',
        'contract',
        'shipper',
        'consignee',
        'city',
        'total_gas_amount',
        'gas_type',
        'date'
    ]
    search_fields = [
        'number',
        'contract',
        'consignee',
        'city'
    ]
    list_filter = ['date', 'gas_type']

@admin.register(RailwayTtn)
class RailwayTtnAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'number',
        'railway_ttn',
        'contract',
        'shipper',
        'carrier',
        'consignee',
        'total_gas_amount_by_scales',
        'total_gas_amount_by_ttn',
        'gas_type',
        'date'
    ]
    search_fields = [
        'number',
        'railway_ttn',
        'contract',
        'shipper__name',
        'consignee__name'
    ]
    list_filter = ['date', 'gas_type']


@admin.register(Contractor)
class ContractorAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'code']
    search_fields = ['name', 'code']


@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ['id', 'name']
    search_fields = ['name']


@admin.register(FilePath)
class FilePathAdmin(admin.ModelAdmin):
    list_display = ['path']
