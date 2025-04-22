from rest_framework import serializers
from ..models import MobileApp


class MobileAppSerializer(serializers.ModelSerializer):
    apk_url = serializers.SerializerMethodField()

    class Meta:
        model = MobileApp
        fields = ['version_name', 'apk_url', 'update_date']

    def get_apk_url(self, obj):
        return self.context['request'].build_absolute_uri(obj.apk_file.url)
