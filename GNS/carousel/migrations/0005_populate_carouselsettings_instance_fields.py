# Data migration: populate number/name/tcp/rfid from env for existing rows

import os

from django.db import migrations


def populate_carousel_settings(apps, schema_editor):
    CarouselSettings = apps.get_model('carousel', 'CarouselSettings')
    ReaderSettings = apps.get_model('filling_station', 'ReaderSettings')

    tcp_host = os.getenv('CAROUSEL_1_TCP_HOST', '').strip()
    tcp_port = int(os.getenv('CAROUSEL_1_TCP_PORT', '4001'))
    reader_number_raw = os.getenv('CAROUSEL_1_RFID_READER', '').strip()
    reader = None
    if reader_number_raw:
        try:
            reader = ReaderSettings.objects.filter(
                number=int(reader_number_raw)
            ).first()
        except (TypeError, ValueError):
            reader = None

    for index, settings in enumerate(
        CarouselSettings.objects.order_by('pk'),
        start=1,
    ):
        settings.number = index
        if not settings.name:
            settings.name = f'Карусель {index}'
        if index == 1:
            if tcp_host:
                settings.tcp_host = tcp_host
            settings.tcp_port = tcp_port
            if reader is not None:
                settings.rfid_reader = reader
        settings.is_active = True
        settings.save()


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('carousel', '0004_carouselsettings_per_instance_fields'),
    ]

    operations = [
        migrations.RunPython(populate_carousel_settings, noop_reverse),
    ]
