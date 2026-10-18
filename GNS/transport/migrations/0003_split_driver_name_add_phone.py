from django.db import migrations, models

import transport.models


def split_full_name(apps, schema_editor):
    Driver = apps.get_model('transport', 'Driver')
    for driver in Driver.objects.all():
        parts = (driver.full_name or '').split()
        driver.last_name = parts[0] if parts else '-'
        driver.first_name = parts[1] if len(parts) > 1 else '-'
        driver.middle_name = ' '.join(parts[2:]) if len(parts) > 2 else ''
        driver.save(update_fields=['last_name', 'first_name', 'middle_name'])


def rebuild_full_name(apps, schema_editor):
    Driver = apps.get_model('transport', 'Driver')
    for driver in Driver.objects.all():
        parts = [driver.last_name, driver.first_name]
        if driver.middle_name:
            parts.append(driver.middle_name)
        driver.full_name = ' '.join(part for part in parts if part)
        driver.save(update_fields=['full_name'])


class Migration(migrations.Migration):

    dependencies = [
        ('transport', '0002_add_driver'),
    ]

    operations = [
        migrations.AddField(
            model_name='driver',
            name='first_name',
            field=models.CharField(blank=True, default='', max_length=50, verbose_name='Имя'),
        ),
        migrations.AddField(
            model_name='driver',
            name='last_name',
            field=models.CharField(blank=True, default='', max_length=50, verbose_name='Фамилия'),
        ),
        migrations.AddField(
            model_name='driver',
            name='middle_name',
            field=models.CharField(blank=True, default='', max_length=50, verbose_name='Отчество'),
        ),
        migrations.AddField(
            model_name='driver',
            name='phone',
            field=models.CharField(
                blank=True,
                default='',
                help_text='Формат: +375(29)123-45-78. Код оператора: 25, 29, 33 или 44.',
                max_length=17,
                validators=[transport.models.validate_belarus_mobile_phone],
                verbose_name='Телефон',
            ),
        ),
        migrations.RunPython(split_full_name, rebuild_full_name),
        migrations.AlterField(
            model_name='driver',
            name='first_name',
            field=models.CharField(max_length=50, verbose_name='Имя'),
        ),
        migrations.AlterField(
            model_name='driver',
            name='last_name',
            field=models.CharField(max_length=50, verbose_name='Фамилия'),
        ),
        migrations.RemoveField(
            model_name='driver',
            name='full_name',
        ),
        migrations.AlterModelOptions(
            name='driver',
            options={
                'ordering': ['last_name', 'first_name'],
                'verbose_name': 'Водитель',
                'verbose_name_plural': 'Водители',
            },
        ),
    ]
