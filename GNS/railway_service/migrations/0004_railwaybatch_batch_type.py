from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('railway_service', '0003_alter_railwaytankhistory_gas_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='railwaybatch',
            name='batch_type',
            field=models.PositiveSmallIntegerField(
                choices=[(0, 'Не определён'), (1, 'Приёмка'), (2, 'Отгрузка')],
                default=0,
                verbose_name='Тип партии',
            ),
        ),
    ]
