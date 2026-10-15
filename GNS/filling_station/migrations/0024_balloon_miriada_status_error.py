from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('filling_station', '0023_balloonsbatch_miriada_status_errors'),
    ]

    operations = [
        migrations.AddField(
            model_name='balloon',
            name='miriada_status_error',
            field=models.TextField(
                blank=True,
                default='',
                help_text='Текст message из ответа Мириады при последней проверке партии',
                verbose_name='Ошибка отправки статуса в Мириаду',
            ),
        ),
    ]
