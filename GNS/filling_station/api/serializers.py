from rest_framework import serializers
from ..models import (Balloon, Truck, Trailer, RailwayTank, TTN, BalloonsLoadingBatch, BalloonsUnloadingBatch,
                      RailwayLoadingBatch, GasLoadingBatch, GasUnloadingBatch)


class BalloonSerializer(serializers.ModelSerializer):
    class Meta:
        model = Balloon
        fields = ['id', 'nfc_tag', 'serial_number', 'creation_date', 'size', 'netto', 'brutto',
                  'current_examination_date', 'next_examination_date', 'status', 'manufacturer', 'wall_thickness',
                  'filling_status', 'update_passport_required']


class TruckSerializer(serializers.ModelSerializer):
    class Meta:
        model = Truck
        fields = ['id', 'car_brand', 'registration_number', 'type', 'max_capacity_cylinders_by_type',
                  'max_weight_of_transported_cylinders', 'max_mass_of_transported_gas', 'empty_weight',
                  'full_weight', 'is_on_station', 'entry_date', 'entry_time', 'departure_date', 'departure_time']


class TrailerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Trailer
        fields = ['id', 'trailer_brand', 'registration_number', 'type', 'truck', 'max_capacity_cylinders_by_type',
                  'max_weight_of_transported_cylinders', 'max_mass_of_transported_gas', 'empty_weight',
                  'full_weight', 'is_on_station', 'entry_date', 'entry_time', 'departure_date', 'departure_time']


class RailwayTanksSerializer(serializers.ModelSerializer):
    class Meta:
        model = RailwayTank
        fields = ['id', 'number', 'empty_weight', 'full_weight', 'gas_amount', 'is_on_station', 'entry_date',
                  'entry_time', 'departure_date', 'departure_time']


class TTNSerializer(serializers.ModelSerializer):
    class Meta:
        model = TTN
        fields = ['id', 'number', 'contract', 'name_of_supplier', 'gas_amount', 'balloons_amount', 'date']


class BalloonsLoadingBatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = BalloonsLoadingBatch
        fields = ['id', 'end_date', 'end_time', 'truck', 'trailer', 'reader_number',
                  'amount_of_rfid', 'amount_of_5_liters', 'amount_of_20_liters', 'amount_of_50_liters', 'gas_amount',
                  'balloons_list', 'is_active', 'ttn']


class BalloonsUnloadingBatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = BalloonsUnloadingBatch
        fields = ['id', 'end_date', 'end_time', 'truck', 'trailer', 'reader_number',
                  'amount_of_rfid', 'amount_of_5_liters', 'amount_of_20_liters', 'amount_of_50_liters', 'gas_amount',
                  'balloons_list', 'is_active', 'ttn']


class RailwayLoadingBatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = RailwayLoadingBatch
        fields = ['id', 'end_date', 'end_time', 'gas_amount', 'railway_tanks_list', 'is_active', 'ttn']


class GasLoadingBatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = GasLoadingBatch
        fields = ['id', 'end_date', 'end_time', 'truck', 'trailer', 'gas_amount', 'weight_gas_amount',
                  'is_active', 'ttn']


class GasUnloadingBatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = GasUnloadingBatch
        fields = ['id', 'end_date', 'end_time', 'truck', 'trailer', 'gas_amount', 'weight_gas_amount',
                  'is_active', 'ttn']
