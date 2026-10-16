from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from ttn.api.status import miriada_ttn_status_to_api
from ttn.models import MiriadaTtn


@extend_schema_field({
    'type': 'integer',
    'enum': [1, 2, 3],
    'description': (
        'Числовой enum: 1=NOT_PROCESSED (не обрабатывалась), '
        '2=ERROR (ошибка при обработке), 3=CLOSED (закрыта)'
    ),
})
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
