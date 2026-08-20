from rest_framework import serializers
from ..models import (
    Balloon,
    Truck,
    Trailer,
    BalloonsBatch,
    BatchStatus,
)
from filling_station.api.batch_status import batch_status_from_api, batch_status_to_api
from filling_station.services.batches import pause_other_active_batches_on_reader

class BatchStatusApiField(serializers.Field):
    """
    API: числовой enum статуса партии.
    0=UNSPECIFIED, 1=ACTIVE, 2=PAUSED, 3=COMPLETED, 4=MIRIADA_ERROR.
    В БД по-прежнему хранится строка (active/paused/...).
    """

    default_error_messages = {
        'invalid': 'Некорректный статус партии. Допустимо: 1=ACTIVE, 2=PAUSED, 3=COMPLETED, 4=MIRIADA_ERROR.',
    }

    def to_representation(self, value):
        return batch_status_to_api(value)

    def to_internal_value(self, data):
        try:
            return batch_status_from_api(data)
        except ValueError:
            self.fail('invalid')


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
            'entry_at',
            'departure_at',
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
            'entry_at',
            'departure_at'
        ]

    def get_type(self, obj):
        return obj.type.type


class BalloonsBatchSerializer(serializers.ModelSerializer):
    batch_type = serializers.CharField(read_only=True)
    ttn_name = serializers.SerializerMethodField()
    status = BatchStatusApiField(
        default=BatchStatus.ACTIVE,
        help_text=(
            'Числовой enum: 1=ACTIVE, 2=PAUSED, 3=COMPLETED, 4=MIRIADA_ERROR '
            '(0=UNSPECIFIED не используется в запросах)'
        ),
    )
    miriada_close_failed = serializers.BooleanField(read_only=True)
    miriada_error_message = serializers.CharField(read_only=True)
    amount_of_ttn = serializers.IntegerField(min_value=1)

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
            'amount_of_sensor',
            'amount_of_ttn',
            'amount_of_5_liters',
            'amount_of_12_liters',
            'amount_of_27_liters',
            'amount_of_50_liters',
            'gas_amount',
            'status',
            'miriada_close_failed',
            'miriada_error_message',
            'ttn_id',
            'ttn_name',
            'balloons_type',
        ]

    def get_ttn_name(self, obj):
        return obj.get_ttn_name()

    def create(self, validated_data):
        instance = super().create(validated_data)
        if instance.status == BatchStatus.ACTIVE:
            pause_other_active_batches_on_reader(instance)
        return instance


# Кастомные сериализаторы для партий приёмки/отгрузки баллонов
class BalloonsTruckSerializer(serializers.ModelSerializer):
    class Meta:
        model = Truck
        fields = ['id', 'car_brand', 'registration_number']


class ActiveBatchSerializer(serializers.ModelSerializer):
    truck = BalloonsTruckSerializer(read_only=True)
    ttn_name = serializers.SerializerMethodField()
    status = BatchStatusApiField(read_only=True)
    miriada_close_failed = serializers.BooleanField(read_only=True)
    miriada_error_message = serializers.CharField(read_only=True)

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
            'amount_of_sensor',
            'amount_of_ttn',
            'amount_of_5_liters',
            'amount_of_12_liters',
            'amount_of_27_liters',
            'amount_of_50_liters',
            'gas_amount',
            'status',
            'miriada_close_failed',
            'miriada_error_message',
            'ttn_id',
            'ttn_name',
            'balloons_type',
        ]

    def get_ttn_name(self, obj):
        return obj.get_ttn_name()


class BalloonAmountSerializer(serializers.ModelSerializer):
    class Meta:
        model = BalloonsBatch
        fields = ['id', 'amount_of_rfid', 'amount_of_sensor', 'amount_of_ttn']
