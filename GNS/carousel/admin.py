from django.contrib import admin
from .models import Carousel, CarouselSettings
from import_export import resources


@admin.register(Carousel)
class CarouselAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'post_number',
        'empty_weight',
        'full_weight',
        'nfc_tag',
        'serial_number',
        'filling_status',
        'change_at',
    ]
    list_filter = [
        'change_at',
    ]
    search_fields = ['post_number', 'nfc_tag', 'serial_number']


@admin.register(CarouselSettings)
class CarouselSettingsAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'read_only',
        'use_weight_management',
        'use_common_correction',
        'weight_correction_value',
        'min_balloon_weight_from',
        'min_balloon_weight_to',
        'max_balloon_weight_from',
        'max_balloon_weight_to',
        'passport_weight_diff_from',
        'passport_weight_diff_to',
    ]
    exclude = ['user']


class CarouselResources(resources.ModelResource):
    class Meta:
        model = Carousel
        fields = (
            'post_number',
            'empty_weight',
            'full_weight',
            'nfc_tag',
            'serial_number',
            'size',
            'netto',
            'brutto',
            'filling_status',
            'change_at',
        )
        export_order = fields
