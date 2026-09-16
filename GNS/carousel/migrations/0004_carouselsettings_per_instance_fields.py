# Generated manually for CarouselSettings per-instance fields

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('carousel', '0003_split_carousel_weight_ranges'),
        ('filling_station', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='carouselsettings',
            name='number',
            field=models.IntegerField(
                null=True,
                verbose_name='Номер карусели',
            ),
        ),
        migrations.AddField(
            model_name='carouselsettings',
            name='name',
            field=models.CharField(
                blank=True,
                default='',
                max_length=100,
                verbose_name='Название',
            ),
        ),
        migrations.AddField(
            model_name='carouselsettings',
            name='tcp_host',
            field=models.CharField(
                blank=True,
                default='',
                max_length=15,
                verbose_name='IP NPort',
            ),
        ),
        migrations.AddField(
            model_name='carouselsettings',
            name='tcp_port',
            field=models.IntegerField(
                default=4001,
                verbose_name='TCP-порт NPort',
            ),
        ),
        migrations.AddField(
            model_name='carouselsettings',
            name='rfid_reader',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='carousels',
                to='filling_station.readersettings',
                verbose_name='RFID-считыватель',
            ),
        ),
        migrations.AddField(
            model_name='carouselsettings',
            name='is_active',
            field=models.BooleanField(
                default=True,
                verbose_name='Активна (listener)',
            ),
        ),
        migrations.AlterModelOptions(
            name='carouselsettings',
            options={
                'ordering': ['number'],
                'verbose_name': 'Настройки карусели',
                'verbose_name_plural': 'Настройки карусели',
            },
        ),
    ]
