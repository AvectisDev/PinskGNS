from django.contrib import admin
from .models import Carousel, CarouselSettings
from import_export import resources


@admin.register(Carousel)
class CarouselAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'carousel_number',
        'post_number',
        'empty_weight',
        'full_weight',
        'nfc_tag',
        'serial_number',
        'filling_status',
        'change_at',
    ]
    list_filter = [
        'carousel_number',
        'change_at',
    ]
    search_fields = ['post_number', 'nfc_tag', 'serial_number']


@admin.register(CarouselSettings)
class CarouselSettingsAdmin(admin.ModelAdmin):
    list_display = [
        'number',
        'name',
        'tcp_host',
        'tcp_port',
        'rfid_reader',
        'is_active',
        'classify_size_by_weight',
        'size_27_empty_weight_max_g',
        'read_only',
        'use_weight_management',
    ]
    list_filter = ['is_active', 'read_only', 'classify_size_by_weight']
    search_fields = ['number', 'name', 'tcp_host']
    exclude = ['user']
    fieldsets = (
        ('Оборудование', {
            'fields': (
                'number',
                'name',
                'tcp_host',
                'tcp_port',
                'rfid_reader',
                'is_active',
            ),
        }),
        ('Классификация объёма', {
            'fields': (
                'classify_size_by_weight',
                'size_27_empty_weight_max_g',
            ),
        }),
        ('Весовая политика', {
            'fields': (
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
            ),
        }),
        ('Корректоры постов', {
            'classes': ('collapse',),
            'fields': tuple(f'post_{i}_correction' for i in range(1, 21)),
        }),
    )


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
