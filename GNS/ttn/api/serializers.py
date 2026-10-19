from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from ttn.api.status import miriada_ttn_status_to_api
from ttn.models import MiriadaTtn


@extend_schema_field({'$ref': '#/components/schemas/MiriadaTtnStatusApiEnum'})
class MiriadaTtnStatusApiField(serializers.Field):
    """API: числовой enum статуса ТТН из Мириады (только чтение)."""

    def to_representation(self, value):
        return miriada_ttn_status_to_api(value)

    def to_internal_value(self, data):
        raise NotImplementedError('Поле status только для чтения')


class MiriadaTtnSerializer(serializers.ModelSerializer):
    status = MiriadaTtnStatusApiField(read_only=True)

    class Meta:
        model = MiriadaTtn
        fields = [
            'name',
            'auto',
            'operation_name',
            'date',
            'ttn_id',
            'status',
        ]
        read_only_fields = fields
