from django.contrib import admin
from .models import Carousel
from import_export import resources

class CarouselResources(resources.ModelResource):
    class Meta:
        model = Carousel
        fields = ('carousel_number', 'is_empty', 'post_number', 'empty_weight', 'full_weight', 'nfc_tag',
                  'serial_number', 'size', 'netto', 'brutto', 'filling_status', 'change_date', 'change_time')
        export_order = fields
