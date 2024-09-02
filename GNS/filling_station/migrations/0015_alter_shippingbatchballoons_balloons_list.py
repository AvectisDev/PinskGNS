# Generated by Django 5.0.6 on 2024-08-20 17:47

import django.contrib.postgres.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('filling_station', '0014_railwaytanks_trailer_ttn_truck_car_brand_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='shippingbatchballoons',
            name='balloons_list',
            field=django.contrib.postgres.fields.ArrayField(base_field=models.CharField(max_length=20), blank=True, null=True, size=None),
        ),
    ]