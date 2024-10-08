# Generated by Django 5.0.6 on 2024-08-05 13:15

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('filling_station', '0002_alter_ballon_state'),
    ]

    operations = [
        migrations.CreateModel(
            name='Truck',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('registration_number', models.CharField(max_length=10, verbose_name='Регистрационный знак')),
                ('type', models.CharField(max_length=50, verbose_name='Тип')),
                ('maximum_capacity_cylinders_by_type', models.IntegerField(blank=True, null=True, verbose_name='Максимальная вместимость баллонов')),
                ('maximum_weight_of_transported_cylinders', models.IntegerField(blank=True, null=True, verbose_name='Максимальная масса перевозимых баллонов')),
                ('maximum_mass_of_transported_gas', models.IntegerField(blank=True, null=True, verbose_name='Максимальная масса перевозимого газа')),
                ('empty_weight', models.IntegerField(blank=True, null=True, verbose_name='Вес пустого транспортного средства')),
                ('full_weight', models.IntegerField(blank=True, null=True, verbose_name='Вес полного транспортного средства')),
            ],
        ),
        migrations.AlterField(
            model_name='balloon',
            name='state',
            field=models.CharField(blank=True, max_length=50, verbose_name='Статус'),
        ),
        migrations.CreateModel(
            name='ChangeBalloonStatus',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('change_status_date', models.DateField(blank=True, null=True, verbose_name='Дата смены статуса')),
                ('change_status_time', models.TimeField(blank=True, null=True, verbose_name='Время смены статуса')),
                ('status', models.CharField(blank=True, max_length=50, verbose_name='Статус')),
                ('cylinder', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='filling_station.balloon')),
            ],
        ),
    ]
