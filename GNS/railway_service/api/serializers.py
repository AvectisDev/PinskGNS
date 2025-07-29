from rest_framework import serializers
from ..models import RailwayBatch


class RailwayBatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = RailwayBatch
        fields = [
            'id',
            'end_date',
            'gas_amount_spbt',
            'gas_amount_pba',
            'railway_tank_list',
            'is_active',
            'import_ttn',
            'export_ttn'
        ]
