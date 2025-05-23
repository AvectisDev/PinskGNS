# Generated by Django 5.1.4 on 2025-04-07 06:03

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('filling_station', '0054_carousel_carrier_consignee_shipper_and_more'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='railwayttn',
            options={'ordering': ['-id', '-date'], 'verbose_name': 'Железнодорожная ТТН', 'verbose_name_plural': 'Железнодорожные ТТН'},
        ),
        migrations.AlterModelOptions(
            name='trailer',
            options={'ordering': ['-is_on_station', '-entry_date', '-entry_time', '-departure_date', '-departure_time'], 'verbose_name': 'Прицеп', 'verbose_name_plural': 'Прицепы'},
        ),
        migrations.AlterModelOptions(
            name='truck',
            options={'ordering': ['-is_on_station', '-entry_date', '-entry_time', '-departure_date', '-departure_time'], 'verbose_name': 'Грузовик', 'verbose_name_plural': 'Грузовики'},
        ),
        migrations.AddField(
            model_name='balloonsloadingbatch',
            name='amount_of_ttn',
            field=models.IntegerField(blank=True, null=True, verbose_name='Количество баллонов по ТТН'),
        ),
        migrations.AddField(
            model_name='balloonsunloadingbatch',
            name='amount_of_ttn',
            field=models.IntegerField(blank=True, null=True, verbose_name='Количество баллонов по ТТН'),
        ),
        migrations.AlterField(
            model_name='balloonsloadingbatch',
            name='ttn',
            field=models.CharField(default='', max_length=20, verbose_name='Номер ТТН'),
        ),
        migrations.AlterField(
            model_name='balloonsunloadingbatch',
            name='ttn',
            field=models.CharField(default='', max_length=20, verbose_name='Номер ТТН'),
        ),
        migrations.CreateModel(
            name='NewTTN',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('number', models.CharField(max_length=100, verbose_name='Номер ТТН')),
                ('contract', models.CharField(blank=True, max_length=100, verbose_name='Номер договора')),
                ('date', models.DateField(blank=True, null=True, verbose_name='Дата формирования накладной')),
                ('carrier', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='balloons_carrier', to='filling_station.carrier', verbose_name='Перевозчик')),
                ('consignee', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='balloons_consignee', to='filling_station.consignee', verbose_name='Грузополучатель')),
                ('loading_batch', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='ttn_loading', to='filling_station.balloonsloadingbatch', verbose_name='Партия приёмки')),
                ('shipper', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='balloons_shipper', to='filling_station.shipper', verbose_name='Грузоотправитель')),
                ('unloading_batch', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='ttn_unloading', to='filling_station.balloonsunloadingbatch', verbose_name='Партия отгрузки')),
            ],
            options={
                'verbose_name': 'ТТН на баллоны',
                'verbose_name_plural': 'ТТН на баллоны',
                'ordering': ['-id', '-date'],
            },
        ),
    ]
