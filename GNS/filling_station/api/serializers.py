from rest_framework import serializers
from ..models import (
    Balloon,
    Truck,
    Trailer,
    BalloonsBatch
)


class BalloonSerializer(serializers.ModelSerializer):
    class Meta:
        model = Balloon
        fields = [
            'nfc_tag',
            'serial_number',
            'creation_date',
            'size',
            'netto',
            'brutto',
            'current_examination_date',
            'next_examination_date',
            'status',
            'manufacturer',
            'wall_thickness',
            'filling_status',
            'update_passport_required'
        ]


class TruckSerializer(serializers.ModelSerializer):
    type = serializers.SerializerMethodField()
    trailer = serializers.SerializerMethodField()

    class Meta:
        model = Truck
        fields = [
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
            'entry_date',
            'entry_time',
            'departure_date',
            'departure_time',
            'trailer'
        ]

    def get_type(self, obj):
        return obj.type.type

    def get_trailer(self, obj):
        trailer = obj.trailer.first()
        if trailer:
            return TrailerSerializer(trailer).data
        return None


class TrailerSerializer(serializers.ModelSerializer):
    type = serializers.SerializerMethodField()

    class Meta:
        model = Trailer
        fields = [
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
            'entry_date',
            'entry_time',
            'departure_date',
            'departure_time'
        ]

    def get_type(self, obj):
        return obj.type.type


class BalloonsBatchSerializer(serializers.ModelSerializer):
    batch_type = serializers.CharField(read_only=True)
    class Meta:
        model = BalloonsBatch
        fields = [
            'id',
            'batch_type',
            'started_at',
            'completed_at',
            'truck',
            'trailer',
            'reader_number',
            'amount_of_rfid',
            'amount_of_5_liters',
            'amount_of_12_liters',
            'amount_of_27_liters',
            'amount_of_50_liters',
            'gas_amount',
            'is_active',
            'ttn',
            'amount_of_ttn'
        ]


# Кастомные сериализаторы для партий приёмки/отгрузки баллонов
class BalloonsTruckSerializer(serializers.ModelSerializer):
    class Meta:
        model = Truck
        fields = ['id', 'car_brand', 'registration_number']


class ActiveBatchSerializer(serializers.ModelSerializer):
    truck = BalloonsTruckSerializer(read_only=True)

    class Meta:
        model = BalloonsBatch
        fields = [
            'id',
            'batch_type',
            'started_at',
            'completed_at',
            'truck',
            'trailer',
            'reader_number',
            'amount_of_rfid',
            'amount_of_5_liters',
            'amount_of_12_liters',
            'amount_of_27_liters',
            'amount_of_50_liters',
            'gas_amount',
            'is_active',
            'ttn',
            'amount_of_ttn'
        ]


class BalloonAmountSerializer(serializers.ModelSerializer):
    class Meta:
        model = BalloonsBatch
        fields = ['id', 'amount_of_rfid']
