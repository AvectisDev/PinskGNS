from rest_framework import serializers
from ..models import AutoGasBatch


class AutoGasBatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = AutoGasBatch
        fields = [
            'id',
            'batch_type',
            'end_date',
            'end_time',
            'truck',
            'trailer',
            'gas_amount',
            'gas_type',
            'scale_empty_weight',
            'scale_full_weight',
            'weight_gas_amount',
            'is_active',
            'ttn'
        ]
