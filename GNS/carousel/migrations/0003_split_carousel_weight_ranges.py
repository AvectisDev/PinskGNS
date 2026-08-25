from django.db import migrations, models


def copy_weight_ranges(apps, schema_editor):
    CarouselSettings = apps.get_model('carousel', 'CarouselSettings')
    for settings in CarouselSettings.objects.all():
        settings.min_balloon_weight_to = settings.min_balloon_weight
        settings.min_balloon_weight_from = round(settings.min_balloon_weight * 0.877, 2)
        settings.max_balloon_weight_to = settings.max_balloon_weight
        settings.max_balloon_weight_from = round(settings.max_balloon_weight - 2.5, 2)
        settings.passport_weight_diff_to = settings.max_passport_weight_diff
        settings.passport_weight_diff_from = 0.0
        settings.save(
            update_fields=[
                'min_balloon_weight_from',
                'min_balloon_weight_to',
                'max_balloon_weight_from',
                'max_balloon_weight_to',
                'passport_weight_diff_from',
                'passport_weight_diff_to',
            ]
        )


class Migration(migrations.Migration):

    dependencies = [
        ('carousel', '0002_carouselsettings_max_passport_weight_diff'),
    ]

    operations = [
        migrations.AddField(
            model_name='carouselsettings',
            name='max_balloon_weight_from',
            field=models.FloatField(default=44.0, verbose_name='Максимальный вес баллона (от)'),
        ),
        migrations.AddField(
            model_name='carouselsettings',
            name='max_balloon_weight_to',
            field=models.FloatField(default=46.5, verbose_name='Максимальный вес баллона (до)'),
        ),
        migrations.AddField(
            model_name='carouselsettings',
            name='min_balloon_weight_from',
            field=models.FloatField(default=15.6, verbose_name='Минимальный вес баллона (от)'),
        ),
        migrations.AddField(
            model_name='carouselsettings',
            name='min_balloon_weight_to',
            field=models.FloatField(default=17.8, verbose_name='Минимальный вес баллона (до)'),
        ),
        migrations.AddField(
            model_name='carouselsettings',
            name='passport_weight_diff_from',
            field=models.FloatField(default=0.0, verbose_name='Разница паспортных весов (от)'),
        ),
        migrations.AddField(
            model_name='carouselsettings',
            name='passport_weight_diff_to',
            field=models.FloatField(default=21.5, verbose_name='Разница паспортных весов (до)'),
        ),
        migrations.RunPython(copy_weight_ranges, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='carouselsettings',
            name='max_balloon_weight',
        ),
        migrations.RemoveField(
            model_name='carouselsettings',
            name='max_passport_weight_diff',
        ),
        migrations.RemoveField(
            model_name='carouselsettings',
            name='min_balloon_weight',
        ),
    ]
