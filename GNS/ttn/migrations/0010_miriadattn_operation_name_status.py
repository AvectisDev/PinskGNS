from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ttn', '0009_alter_ttn_date_auto_now_add'),
    ]

    operations = [
        migrations.AddField(
            model_name='miriadattn',
            name='operation_name',
            field=models.CharField(
                blank=True,
                default='',
                max_length=100,
                verbose_name='Операция',
            ),
        ),
        migrations.AddField(
            model_name='miriadattn',
            name='status',
            field=models.CharField(
                choices=[
                    ('not_processed', 'Не обрабатывалась'),
                    ('error', 'Ошибка при обработке'),
                    ('closed', 'Закрыта'),
                ],
                db_index=True,
                default='not_processed',
                max_length=20,
                verbose_name='Статус',
            ),
        ),
    ]
