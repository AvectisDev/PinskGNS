"""Удаление служебного прицепа «-» / «Не указан»: FK обнуляем, запись удаляем."""

from django.db import migrations


def remove_placeholder_trailer(apps, schema_editor):
    Trailer = apps.get_model('filling_station', 'Trailer')
    BalloonsBatch = apps.get_model('filling_station', 'BalloonsBatch')
    AutoGasBatch = apps.get_model('autogas', 'AutoGasBatch')

    placeholders = Trailer.objects.filter(registration_number__in=['-', '—', 'не указан', 'неуказан'])
    placeholder_ids = list(placeholders.values_list('pk', flat=True))
    if not placeholder_ids:
        return

    BalloonsBatch.objects.filter(trailer_id__in=placeholder_ids).update(trailer_id=None)
    AutoGasBatch.objects.filter(trailer_id__in=placeholder_ids).update(trailer_id=None)
    placeholders.delete()


class Migration(migrations.Migration):

    dependencies = [
        ('filling_station', '0019_transliterate_registration_numbers'),
        ('autogas', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(remove_placeholder_trailer, migrations.RunPython.noop),
    ]
