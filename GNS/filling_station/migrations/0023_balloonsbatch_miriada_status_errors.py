from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('filling_station', '0022_remove_balloonsbatch_amount_of_rfid'),
    ]

    operations = [
        migrations.AddField(
            model_name='balloonsbatch',
            name='miriada_status_errors',
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text='Словарь NFC → текст ошибки из ответа Мириады',
                verbose_name='Ошибки отправки статусов баллонов в Мириаду',
            ),
        ),
    ]
