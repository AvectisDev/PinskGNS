# Generated by Django 5.0.6 on 2024-10-22 10:42

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('filling_station', '0046_remove_trailer_type_remove_truck_type'),
    ]

    operations = [
        migrations.RenameField(
            model_name='trailer',
            old_name='new_type',
            new_name='type',
        ),
        migrations.RenameField(
            model_name='truck',
            old_name='new_type',
            new_name='type',
        ),
    ]
