from rest_framework import serializers
from ..models import (Balloon, Truck, Trailer, RailwayTank, TTN, BalloonsLoadingBatch, BalloonsUnloadingBatch,
                      RailwayBatch, AutoGasBatch)


class BalloonSerializer(serializers.ModelSerializer):
    class Meta:
        model = Balloon
        fields = ['id', 'nfc_tag', 'serial_number', 'creation_date', 'size', 'netto', 'brutto',
                  'current_examination_date', 'next_examination_date', 'status', 'manufacturer', 'wall_thickness',
                  'filling_status', 'update_passport_required']


class TruckSerializer(serializers.ModelSerializer):
    class Meta:
        model = Truck
        fields = ['id', 'car_brand', 'registration_number', 'type', 'capacity_cylinders',
                  'max_weight_of_transported_cylinders', 'max_mass_of_transported_gas', 'max_gas_volume',
                  'empty_weight', 'full_weight', 'is_on_station', 'entry_date', 'entry_time', 'departure_date',
                  'departure_time']


class TrailerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Trailer
        fields = ['id', 'truck', 'trailer_brand', 'registration_number', 'type', 'capacity_cylinders',
                  'max_weight_of_transported_cylinders', 'max_mass_of_transported_gas', 'max_gas_volume', 'empty_weight',
                  'full_weight', 'is_on_station', 'entry_date', 'entry_time', 'departure_date', 'departure_time']


class RailwayTankSerializer(serializers.ModelSerializer):
    class Meta:
        model = RailwayTank
        fields = ['id', 'registration_number', 'empty_weight', 'full_weight', 'gas_weight', 'gas_type', 'is_on_station',
                  'entry_date', 'entry_time', 'departure_date', 'departure_time']


class TTNSerializer(serializers.ModelSerializer):
    class Meta:
        model = TTN
        fields = ['id', 'number', 'contract', 'shipper', 'consignee', 'gas_amount', 'gas_type', 'balloons_amount',
                  'date']


class BalloonsLoadingBatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = BalloonsLoadingBatch
        fields = ['id', 'begin_date', 'begin_time', 'end_date', 'end_time', 'truck', 'trailer', 'reader_number',
                  'amount_of_rfid', 'amount_of_5_liters', 'amount_of_12_liters', 'amount_of_27_liters',
                  'amount_of_50_liters', 'gas_amount', 'is_active', 'ttn']


class BalloonsUnloadingBatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = BalloonsUnloadingBatch
        fields = ['id', 'begin_date', 'begin_time', 'end_date', 'end_time', 'truck', 'trailer', 'reader_number',
                  'amount_of_rfid', 'amount_of_5_liters', 'amount_of_12_liters', 'amount_of_27_liters',
                  'amount_of_50_liters', 'gas_amount', 'is_active', 'ttn']


# Кастомные сериализаторы для партий приёмки/отгрузки баллонов
class BalloonsTruckSerializer(serializers.ModelSerializer):
    class Meta:
        model = Truck
        fields = ['id', 'car_brand', 'registration_number']


class BalloonsLoadBatchSerializer(serializers.ModelSerializer):
    truck = BalloonsTruckSerializer(read_only=True)

    class Meta:
        model = BalloonsLoadingBatch
        fields = ['id', 'begin_date', 'begin_time', 'truck', 'reader_number']


class BalloonsUnloadBatchSerializer(serializers.ModelSerializer):
    truck = BalloonsTruckSerializer(read_only=True)

    class Meta:
        model = BalloonsUnloadingBatch
        fields = ['id', 'begin_date', 'begin_time', 'truck', 'reader_number']


class RailwayLoadingBatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = RailwayBatch
        fields = ['id', 'end_date', 'end_time', 'gas_amount_spbt', 'gas_amount_pba', 'railway_tank_list', 'is_active',
                  'ttn']


class AutoGasBatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = AutoGasBatch
        fields = ['id', 'batch_type', 'end_date', 'end_time', 'truck', 'trailer', 'gas_amount', 'gas_type',
                  'scale_empty_weight', 'scale_full_weight', 'weight_gas_amount', 'is_active', 'ttn']
