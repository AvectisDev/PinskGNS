# Generated by Django 5.0.6 on 2024-10-22 10:07

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('filling_station', '0045_trailer_new_type'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='trailer',
            name='type',
        ),
        migrations.RemoveField(
            model_name='truck',
            name='type',
        ),
    ]
