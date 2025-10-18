from rest_framework import serializers
from autogas.models import AutoGasBatch


class AutoGasBatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = AutoGasBatch
        fields = [
            'id',
            'batch_type',
            'begin_at',
            'completed_at',
            'truck',
            'trailer',
            'gas_amount',
            'gas_type',
            'scale_empty_weight',
            'scale_full_weight',
            'weight_gas_amount',
            'is_active',
        ]
