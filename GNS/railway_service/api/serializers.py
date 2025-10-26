from rest_framework import serializers
from railway_service.models import RailwayBatch


class RailwayBatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = RailwayBatch
        fields = [
            'id',
            'begin_date',
            'end_date',
            'gas_amount_spbt',
            'gas_amount_pba',
            'railway_tank_list',
            'is_active',
        ]
