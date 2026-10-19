"""Сериализаторы API грузовиков и прицепов."""

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from transport.models import Driver, Trailer, Truck


class DriverSerializer(serializers.ModelSerializer):
    """Сериализатор водителя для вложенного вывода у грузовика."""

    class Meta:
        model = Driver
        fields = [
            'id',
            'last_name',
            'first_name',
            'middle_name',
            'phone',
        ]


class TrailerSerializer(serializers.ModelSerializer):
    """Сериализатор прицепа с типом транспорта."""

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
            'is_active',
            'entry_at',
            'departure_at',
        ]

    @extend_schema_field(serializers.CharField())
    def get_type(self, obj):
        return obj.type.type


class TruckSerializer(serializers.ModelSerializer):
    """Сериализатор грузовика с типом, водителем и прицепом."""

    type = serializers.SerializerMethodField()
    driver = DriverSerializer(read_only=True)
    trailer = serializers.SerializerMethodField()

    class Meta:
        model = Truck
        fields = [
            'id',
            'car_brand',
            'registration_number',
            'type',
            'driver',
            'capacity_cylinders',
            'max_weight_of_transported_cylinders',
            'max_mass_of_transported_gas',
            'max_gas_volume',
            'empty_weight',
            'full_weight',
            'is_on_station',
            'is_active',
            'entry_at',
            'departure_at',
            'trailer',
        ]

    @extend_schema_field(serializers.CharField())
    def get_type(self, obj):
        return obj.type.type

    @extend_schema_field(TrailerSerializer)
    def get_trailer(self, obj):
        trailer = obj.trailer.first()
        if trailer:
            return TrailerSerializer(trailer).data
        return None
