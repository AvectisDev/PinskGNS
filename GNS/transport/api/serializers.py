"""Сериализаторы API грузовиков и прицепов."""

from rest_framework import serializers

from transport.models import Trailer, Truck


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

    def get_type(self, obj):
        return obj.type.type


class TruckSerializer(serializers.ModelSerializer):
    """Сериализатор грузовика с типом и прицепом."""

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
            'is_active',
            'entry_at',
            'departure_at',
            'trailer',
        ]

    def get_type(self, obj):
        return obj.type.type

    def get_trailer(self, obj):
        trailer = obj.trailer.first()
        if trailer:
            return TrailerSerializer(trailer).data
        return None
