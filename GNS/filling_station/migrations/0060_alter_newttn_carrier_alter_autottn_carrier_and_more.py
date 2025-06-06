# Generated by Django 5.1.4 on 2025-04-10 19:08

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('filling_station', '0059_contractor'),
    ]

    operations = [
        migrations.AlterField(
            model_name='newttn',
            name='carrier',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='balloons_carrier', to='filling_station.contractor', verbose_name='Перевозчик'),
        ),
        migrations.AlterField(
            model_name='autottn',
            name='carrier',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='auto_tank_carrier', to='filling_station.contractor', verbose_name='Перевозчик'),
        ),
        migrations.AlterField(
            model_name='railwayttn',
            name='carrier',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='railway_tank_carrier', to='filling_station.contractor', verbose_name='Перевозчик'),
        ),
        migrations.AlterField(
            model_name='newttn',
            name='consignee',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='balloons_consignee', to='filling_station.contractor', verbose_name='Грузополучатель'),
        ),
        migrations.AlterField(
            model_name='autottn',
            name='consignee',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='auto_tank_consignee', to='filling_station.contractor', verbose_name='Грузополучатель'),
        ),
        migrations.AlterField(
            model_name='railwayttn',
            name='consignee',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='railway_tank_consignee', to='filling_station.contractor', verbose_name='Грузополучатель'),
        ),
        migrations.AlterField(
            model_name='railwayttn',
            name='shipper',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='railway_tank_shipper', to='filling_station.contractor', verbose_name='Грузоотправитель'),
        ),
        migrations.AlterField(
            model_name='autottn',
            name='shipper',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='auto_tank_shipper', to='filling_station.contractor', verbose_name='Грузоотправитель'),
        ),
        migrations.AlterField(
            model_name='newttn',
            name='shipper',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='balloons_shipper', to='filling_station.contractor', verbose_name='Грузоотправитель'),
        ),
        migrations.DeleteModel(
            name='Carrier',
        ),
        migrations.DeleteModel(
            name='Consignee',
        ),
        migrations.DeleteModel(
            name='Shipper',
        ),
    ]
