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

    def validate(self, attrs):
        is_active = attrs.get('is_active', getattr(self.instance, 'is_active', False))
        if is_active:
            active_qs = AutoGasBatch.objects.filter(is_active=True)
            if self.instance is not None:
                active_qs = active_qs.exclude(pk=self.instance.pk)
            if active_qs.exists():
                raise serializers.ValidationError(
                    {'is_active': 'Уже есть активная партия'}
                )
        return attrs
