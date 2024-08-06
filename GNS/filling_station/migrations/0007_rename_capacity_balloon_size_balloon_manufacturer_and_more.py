# Generated by Django 5.0.6 on 2024-08-06 07:16

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('filling_station', '0006_rename_full_weight_balloon_brutto_and_more'),
    ]

    operations = [
        migrations.RenameField(
            model_name='balloon',
            old_name='capacity',
            new_name='size',
        ),
        migrations.AddField(
            model_name='balloon',
            name='manufacturer',
            field=models.CharField(blank=True, max_length=30, null=True, verbose_name='Производитель'),
        ),
        migrations.AddField(
            model_name='balloon',
            name='wall_thickness',
            field=models.FloatField(blank=True, null=True, verbose_name='Толщина стенок'),
        ),
    ]
