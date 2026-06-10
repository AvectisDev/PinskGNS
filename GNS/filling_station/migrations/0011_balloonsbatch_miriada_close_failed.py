from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('filling_station', '0010_dailyreadercounter_uniq_number_day'),
    ]

    operations = [
        migrations.AddField(
            model_name='balloonsbatch',
            name='miriada_close_failed',
            field=models.BooleanField(
                default=False,
                verbose_name='Ошибка закрытия ТТН в Мириаде',
            ),
        ),
    ]
