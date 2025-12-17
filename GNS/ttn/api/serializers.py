from rest_framework import serializers
from ttn.models import MiriadaTtn


class MiriadaTtnSerializer(serializers.ModelSerializer):
    class Meta:
        model = MiriadaTtn
        fields = [
            'ttn_id',
            'name',
            'auto',
            'date',
        ]


class TtnListItemSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    auto = serializers.CharField()
    date = serializers.DateTimeField(allow_null=True)


class TtnListResponseSerializer(serializers.Serializer):
    ttn_list = TtnListItemSerializer(many=True)

