from django.contrib import admin
from filling_station import models
from import_export import resources


class BalloonResources(resources.ModelResource):
    class Meta:
        model = models.Balloon
        fields = ['nfc_tag', 'serial_number', 'size', 'netto', 'brutto', 'filling_status', "change_date", "change_time"]


@admin.register(models.Balloon)
class BalloonAdmin(admin.ModelAdmin):
    list_display = ['id', 'nfc_tag', 'serial_number', 'creation_date', 'size', 'netto', 'brutto',
                    'current_examination_date', 'next_examination_date', 'diagnostic_date', 'working_pressure',
                    'status', 'manufacturer', 'wall_thickness', 'filling_status', 'update_passport_required']
    search_fields = ['nfc_tag', 'serial_number', 'creation_date', 'size', 'manufacturer']


@admin.register(models.Truck)
class TruckAdmin(admin.ModelAdmin):
    list_display = ['id', 'car_brand', 'registration_number', 'type', 'capacity_cylinders',
                    'max_weight_of_transported_cylinders', 'max_mass_of_transported_gas', 'max_gas_volume',
                    'empty_weight', 'full_weight', 'is_on_station', 'entry_date', 'entry_time', 'departure_date',
                    'departure_time']
    search_fields = ['car_brand', 'registration_number', 'type', 'is_on_station', 'entry_date', 'departure_date']


@admin.register(models.TruckType)
class TruckTypeAdmin(admin.ModelAdmin):
    list_display = ['id', 'type']


@admin.register(models.Trailer)
class TrailerAdmin(admin.ModelAdmin):
    list_display = ['id', 'truck', 'trailer_brand', 'registration_number', 'type', 'capacity_cylinders',
                    'max_weight_of_transported_cylinders', 'max_mass_of_transported_gas', 'max_gas_volume', 'empty_weight',
                    'full_weight', 'is_on_station', 'entry_date', 'entry_time', 'departure_date', 'departure_time']
    search_fields = ['trailer_brand', 'registration_number', 'type', 'is_on_station']


@admin.register(models.TrailerType)
class TrailerTypeAdmin(admin.ModelAdmin):
    list_display = ['id', 'type']


@admin.register(models.TTN)
class TTNAdmin(admin.ModelAdmin):
    list_display = ['id', 'number', 'contract', 'shipper', 'consignee', 'date']
    search_fields = ['number', 'contract', 'consignee']
    list_filter = ['date']


@admin.register(models.BalloonsLoadingBatch)
class BalloonsLoadingBatchAdmin(admin.ModelAdmin):
    list_display = ['id', 'begin_date', 'begin_time', 'end_date', 'end_time', 'truck', 'trailer', 'reader_number',
                    'amount_of_rfid', 'amount_of_5_liters', 'amount_of_12_liters', 'amount_of_27_liters',
                    'amount_of_50_liters', 'gas_amount', 'is_active', 'ttn', 'amount_of_ttn']
    list_filter = ['begin_date', 'end_date', 'is_active']
    search_fields = ['begin_date', 'end_date', 'truck', 'is_active', 'ttn']


@admin.register(models.BalloonsUnloadingBatch)
class BalloonsUnloadingBatchAdmin(admin.ModelAdmin):
    list_display = ['id', 'begin_date', 'begin_time', 'end_date', 'end_time', 'truck', 'trailer', 'reader_number',
                    'amount_of_rfid', 'amount_of_5_liters', 'amount_of_12_liters', 'amount_of_27_liters',
                    'amount_of_50_liters', 'gas_amount', 'is_active', 'ttn', 'amount_of_ttn']
    list_filter = ['begin_date', 'end_date', 'is_active']
    search_fields = ['begin_date', 'end_date', 'truck', 'is_active', 'ttn']


@admin.register(models.AutoGasBatch)
class AutoGasBatchAdmin(admin.ModelAdmin):
    list_display = ['id', 'batch_type', 'end_date', 'end_time', 'truck', 'trailer', 'gas_amount', 'gas_type',
                    'scale_empty_weight', 'scale_full_weight', 'weight_gas_amount', 'is_active']
    list_filter = ['begin_date', 'end_date', 'is_active']
    search_fields = ['begin_date', 'end_date', 'truck', 'is_active']


@admin.register(models.AutoGasBatchSettings)
class AutoGasBatchSettingsAdmin(admin.ModelAdmin):
    list_display = ['id', 'weight_source']


@admin.register(models.AutoTtn)
class AutoTtnAdmin(admin.ModelAdmin):
    list_display = ['id', 'number', 'contract', 'shipper', 'consignee', 'total_gas_amount', 'gas_type', 'date']
    search_fields = ['number', 'contract', 'shipper', 'consignee']
    list_filter = ['date']


@admin.register(models.FilePath)
class FilePathAdmin(admin.ModelAdmin):
    list_display = ('path',)


@admin.register(models.RailwayTank)
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


@admin.register(models.RailwayBatch)
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


@admin.register(models.RailwayTtn)
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
    search_fields = ['number', 'railway_ttn', 'contract', 'shipper__name', 'consignee__name']
    list_filter = ['date', 'gas_type']


@admin.register(models.Contractor)
class ContractorAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'code']
    search_fields = ['name', 'code']
