from rest_framework import serializers
from railway_service.models import RailwayBatch


class RailwayBatchSerializer(serializers.ModelSerializer):
    batch_type_display = serializers.CharField(
        source='get_batch_type_display',
        read_only=True,
    )

    class Meta:
        model = RailwayBatch
        fields = [
            'id',
            'started_at',
            'completed_at',
            'batch_type',
            'batch_type_display',
            'gas_amount_spbt',
            'gas_amount_pba',
            'railway_tank_list',
            'is_active',
        ]
