from rest_framework import serializers
from ..models import Carousel, CarouselSettings


class CarouselSerializer(serializers.ModelSerializer):
    class Meta:
        model = Carousel
        fields = '__all__'


class CarouselSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = CarouselSettings
        fields = '__all__'
