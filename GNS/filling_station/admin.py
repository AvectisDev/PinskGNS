from django.contrib import admin
from .models import (Balloon, Truck, Trailer, RailwayTanks, TTN, BalloonsLoadingBatch, BalloonsUnloadingBatch,
                     RailwayLoadingBatch, GasLoadingBatch, GasUnloadingBatch)
from import_export import resources


class BalloonResources(resources.ModelResource):
    class Meta:
        model = Balloon
        fields = ['id', 'nfc_tag', 'serial_number', 'creation_date', 'size', 'netto', 'brutto',
                  'current_examination_date', 'next_examination_date', 'manufacturer', 'wall_thickness', 'status']


@admin.register(Balloon)
class BalloonAdmin(admin.ModelAdmin):
    list_display = ['id', 'nfc_tag', 'serial_number', 'creation_date', 'size', 'netto', 'brutto',
                    'current_examination_date', 'next_examination_date', 'status', 'manufacturer', 'wall_thickness',
                    'filling_status', 'update_passport_required']
    search_fields = ['nfc_tag', 'serial_number', 'creation_date', 'size', 'manufacturer']
    ordering = ['-id']


@admin.register(Truck)
class TruckAdmin(admin.ModelAdmin):
    list_display = ['id', 'car_brand', 'registration_number', 'type', 'max_capacity_cylinders_by_type',
                    'max_weight_of_transported_cylinders', 'max_mass_of_transported_gas', 'empty_weight',
                    'full_weight', 'is_on_station', 'entry_date', 'entry_time', 'departure_date', 'departure_time']
    search_fields = ['car_brand', 'registration_number', 'type', 'is_on_station', 'entry_date', 'departure_date']
    ordering = ['id']


@admin.register(Trailer)
class TrailerAdmin(admin.ModelAdmin):
    list_display = ['id', 'trailer_brand', 'registration_number', 'type', 'max_capacity_cylinders_by_type',
                    'max_weight_of_transported_cylinders', 'max_mass_of_transported_gas', 'empty_weight',
                    'full_weight', 'is_on_station']
    search_fields = ['trailer_brand', 'registration_number', 'type', 'is_on_station']
    ordering = ['id']


@admin.register(RailwayTanks)
class RailwayTanksAdmin(admin.ModelAdmin):
    list_display = ['id', 'number', 'empty_weight', 'full_weight', 'is_on_station', 'entry_date', 'entry_time',
                    'departure_date', 'departure_time']
    search_fields = ['number', 'is_on_station', 'entry_date', 'departure_date']
    ordering = ['-id']


@admin.register(TTN)
class TTNAdmin(admin.ModelAdmin):
    list_display = ['id', 'number', 'contract', 'name_of_supplier', 'gas_amount', 'balloons_amount', 'date']
    search_fields = ['number', 'contract', 'name_of_supplier', 'date']
    list_filter = ['date']
    ordering = ['-id']


@admin.register(BalloonsLoadingBatch)
class LoadingBatchBalloonsAdmin(admin.ModelAdmin):
    list_display = ['id', 'begin_date', 'begin_time', 'end_date', 'end_time', 'truck', 'trailer', 'reader_number',
                    'amount_of_rfid', 'amount_of_5_liters', 'amount_of_20_liters', 'amount_of_50_liters', 'gas_amount',
                    'balloons_list', 'is_active', 'ttn']
    list_filter = ['begin_date', 'end_date', 'is_active']
    search_fields = ['begin_date', 'end_date', 'truck', 'is_active', 'ttn']
    ordering = ['-id']


@admin.register(BalloonsUnloadingBatch)
class UnloadingBatchBalloonsAdmin(admin.ModelAdmin):
    list_display = ['id', 'begin_date', 'begin_time', 'end_date', 'end_time', 'truck', 'trailer',
                    'amount_of_rfid', 'amount_of_5_liters', 'amount_of_20_liters', 'amount_of_50_liters', 'gas_amount',
                    'balloons_list', 'is_active', 'ttn']
    list_filter = ['begin_date', 'end_date', 'is_active']
    search_fields = ['begin_date', 'end_date', 'truck', 'is_active', 'ttn']
    ordering = ['-id']


@admin.register(RailwayLoadingBatch)
class LoadingBatchRailwayAdmin(admin.ModelAdmin):
    list_display = ['id', 'begin_date', 'begin_time', 'end_date', 'end_time', 'gas_amount', 'railway_tanks_list',
                    'is_active', 'ttn']
    list_filter = ['begin_date', 'end_date', 'is_active']
    search_fields = ['begin_date', 'end_date', 'is_active', 'ttn']
    ordering = ['-id']


@admin.register(GasLoadingBatch)
class LoadingBatchGasAdmin(admin.ModelAdmin):
    list_display = ['id', 'begin_date', 'begin_time', 'end_date', 'end_time', 'truck', 'trailer',
                    'gas_amount', 'is_active', 'ttn']
    list_filter = ['begin_date', 'end_date', 'is_active']
    search_fields = ['begin_date', 'end_date', 'truck', 'is_active', 'ttn']
    ordering = ['-id']


@admin.register(GasUnloadingBatch)
class UnloadingBatchGasAdmin(admin.ModelAdmin):
    list_display = ['id', 'begin_date', 'begin_time', 'end_date', 'end_time', 'truck', 'trailer',
                    'gas_amount', 'is_active', 'ttn']
    list_filter = ['begin_date', 'end_date', 'is_active']
    search_fields = ['begin_date', 'end_date', 'truck', 'is_active', 'ttn']
    ordering = ['-id']

