# Generated by Django 5.0.6 on 2024-08-07 18:53

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('filling_station', '0010_balloonamount_change_time_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='balloon',
            name='change_date',
            field=models.DateField(auto_now_add=True, null=True, verbose_name='Дата изменений'),
        ),
        migrations.AddField(
            model_name='balloon',
            name='change_time',
            field=models.TimeField(auto_now_add=True, null=True, verbose_name='Время изменений'),
        ),
        migrations.DeleteModel(
            name='ChangeBalloonStatus',
        ),
    ]
