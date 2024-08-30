# Generated by Django 5.0.6 on 2024-08-30 10:50

import django.contrib.postgres.fields
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('filling_station', '0023_alter_loadingbatchballoons_options_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RenameModel(
            old_name='LoadingBatchGas',
            new_name='GasLoadingBatch',
        ),
        migrations.RenameModel(
            old_name='UnloadingBatchGas',
            new_name='GasUnloadingBatch',
        ),
        migrations.RenameModel(
            old_name='LoadingBatchRailway',
            new_name='RailwayLoadingBatch',
        ),
        migrations.RemoveField(
            model_name='unloadingbatchballoons',
            name='trailer',
        ),
        migrations.RemoveField(
            model_name='unloadingbatchballoons',
            name='truck',
        ),
        migrations.RemoveField(
            model_name='unloadingbatchballoons',
            name='ttn',
        ),
        migrations.RemoveField(
            model_name='unloadingbatchballoons',
            name='user',
        ),
        migrations.CreateModel(
            name='BalloonsLoadingBatch',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('begin_date', models.DateField(auto_now_add=True, null=True, verbose_name='Дата начала приёмки')),
                ('begin_time', models.TimeField(auto_now_add=True, null=True, verbose_name='Время начала приёмки')),
                ('end_date', models.DateField(blank=True, null=True, verbose_name='Дата окончания приёмки')),
                ('end_time', models.TimeField(blank=True, null=True, verbose_name='Время окончания приёмки')),
                ('reader_number', models.IntegerField(blank=True, null=True, verbose_name='Номер считывателя')),
                ('amount_of_rfid', models.IntegerField(blank=True, null=True, verbose_name='Количество баллонов по rfid')),
                ('amount_of_5_liters', models.IntegerField(blank=True, default=0, null=True, verbose_name='Количество 5л баллонов')),
                ('amount_of_20_liters', models.IntegerField(blank=True, default=0, null=True, verbose_name='Количество 20л баллонов')),
                ('amount_of_50_liters', models.IntegerField(blank=True, default=0, null=True, verbose_name='Количество 50л баллонов')),
                ('gas_amount', models.FloatField(blank=True, null=True, verbose_name='Количество принятого газа')),
                ('balloons_list', django.contrib.postgres.fields.ArrayField(base_field=models.CharField(max_length=20), blank=True, null=True, size=None)),
                ('is_active', models.BooleanField(blank=True, null=True, verbose_name='В работе')),
                ('trailer', models.ForeignKey(blank=True, default=0, null=True, on_delete=django.db.models.deletion.DO_NOTHING, to='filling_station.trailer', verbose_name='Прицеп')),
                ('truck', models.ForeignKey(on_delete=django.db.models.deletion.DO_NOTHING, to='filling_station.truck', verbose_name='Автомобиль')),
                ('ttn', models.ForeignKey(default=0, on_delete=django.db.models.deletion.DO_NOTHING, to='filling_station.ttn', verbose_name='ТТН')),
                ('user', models.ForeignKey(default=1, on_delete=django.db.models.deletion.DO_NOTHING, to=settings.AUTH_USER_MODEL, verbose_name='Пользователь')),
            ],
            options={
                'verbose_name': 'Партия приёмки баллонов',
                'verbose_name_plural': 'Партии приёмки баллонов',
                'ordering': ['-id'],
            },
        ),
        migrations.CreateModel(
            name='BalloonsUnloadingBatch',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('begin_date', models.DateField(auto_now_add=True, null=True, verbose_name='Дата начала отгрузки')),
                ('begin_time', models.TimeField(auto_now_add=True, null=True, verbose_name='Время начала отгрузки')),
                ('end_date', models.DateField(blank=True, null=True, verbose_name='Дата окончания отгрузки')),
                ('end_time', models.TimeField(blank=True, null=True, verbose_name='Время окончания отгрузки')),
                ('reader_number', models.IntegerField(blank=True, null=True, verbose_name='Номер считывателя')),
                ('amount_of_rfid', models.IntegerField(blank=True, null=True, verbose_name='Количество баллонов по rfid')),
                ('amount_of_5_liters', models.IntegerField(blank=True, default=0, null=True, verbose_name='Количество 5л баллонов')),
                ('amount_of_20_liters', models.IntegerField(blank=True, default=0, null=True, verbose_name='Количество 20л баллонов')),
                ('amount_of_50_liters', models.IntegerField(blank=True, default=0, null=True, verbose_name='Количество 50л баллонов')),
                ('gas_amount', models.FloatField(blank=True, null=True, verbose_name='Количество отгруженного газа')),
                ('balloons_list', django.contrib.postgres.fields.ArrayField(base_field=models.CharField(max_length=20), blank=True, size=None)),
                ('is_active', models.BooleanField(blank=True, null=True, verbose_name='В работе')),
                ('trailer', models.ForeignKey(blank=True, default=0, null=True, on_delete=django.db.models.deletion.DO_NOTHING, to='filling_station.trailer', verbose_name='Прицеп')),
                ('truck', models.ForeignKey(on_delete=django.db.models.deletion.DO_NOTHING, to='filling_station.truck', verbose_name='Автомобиль')),
                ('ttn', models.ForeignKey(default=0, on_delete=django.db.models.deletion.DO_NOTHING, to='filling_station.ttn', verbose_name='ТТН')),
                ('user', models.ForeignKey(default=1, on_delete=django.db.models.deletion.DO_NOTHING, to=settings.AUTH_USER_MODEL, verbose_name='Пользователь')),
            ],
            options={
                'verbose_name': 'Партия отгрузки баллонов',
                'verbose_name_plural': 'Партии отгрузки баллонов',
                'ordering': ['-id'],
            },
        ),
        migrations.DeleteModel(
            name='LoadingBatchBalloons',
        ),
        migrations.DeleteModel(
            name='UnloadingBatchBalloons',
        ),
    ]
