from rest_framework import serializers
from ..models import CarouselSettings


class CarouselSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = CarouselSettings
        fields = '__all__'
