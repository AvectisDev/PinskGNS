# Generated by Django 5.0.6 on 2024-09-22 20:44

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('filling_station', '0034_remove_gasunloadingbatch_trailer_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='autogasbatch',
            name='batch_type',
            field=models.CharField(choices=[('l', 'Приёмка'), ('u', 'Отгрузка')], default='u', max_length=10, verbose_name='Тип партии'),
        ),
    ]
