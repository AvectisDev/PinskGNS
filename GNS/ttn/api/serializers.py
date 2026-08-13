from rest_framework import serializers
from ttn.models import MiriadaTtn


class MiriadaTtnSerializer(serializers.ModelSerializer):
    class Meta:
        model = MiriadaTtn
        fields = [
            'name',
            'auto',
            'date',
            'ttn_id',
        ]
