# Generated by Django 5.0.6 on 2024-08-06 06:17

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('filling_station', '0003_truck_alter_balloon_state_changeballoonstatus'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='truck',
            options={'verbose_name': 'Грузовик', 'verbose_name_plural': 'Грузовики'},
        ),
        migrations.RenameField(
            model_name='changeballoonstatus',
            old_name='cylinder',
            new_name='balloon',
        ),
        migrations.RenameField(
            model_name='truck',
            old_name='maximum_capacity_cylinders_by_type',
            new_name='max_capacity_cylinders_by_type',
        ),
        migrations.RenameField(
            model_name='truck',
            old_name='maximum_mass_of_transported_gas',
            new_name='max_mass_of_transported_gas',
        ),
        migrations.RenameField(
            model_name='truck',
            old_name='maximum_weight_of_transported_cylinders',
            new_name='max_weight_of_transported_cylinders',
        ),
        migrations.AddField(
            model_name='balloon',
            name='status',
            field=models.CharField(blank=True, max_length=100, verbose_name='Статус'),
        ),
        migrations.AlterField(
            model_name='balloon',
            name='state',
            field=models.CharField(blank=True, max_length=100, verbose_name='Статус'),
        ),
        migrations.AlterField(
            model_name='changeballoonstatus',
            name='status',
            field=models.CharField(blank=True, max_length=100, verbose_name='Статус'),
        ),
        migrations.AlterField(
            model_name='truck',
            name='empty_weight',
            field=models.IntegerField(blank=True, null=True, verbose_name='Вес пустого т/с'),
        ),
        migrations.AlterField(
            model_name='truck',
            name='full_weight',
            field=models.IntegerField(blank=True, null=True, verbose_name='Вес полного т/с'),
        ),
    ]
