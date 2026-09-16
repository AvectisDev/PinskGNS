from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('carousel', '0006_carouselsettings_number_unique'),
    ]

    operations = [
        migrations.AddField(
            model_name='carouselsettings',
            name='classify_size_by_weight',
            field=models.BooleanField(
                default=False,
                verbose_name='Определять объём (27/50) по весу пустого баллона',
            ),
        ),
        migrations.AddField(
            model_name='carouselsettings',
            name='size_27_empty_weight_max_g',
            field=models.PositiveIntegerField(
                default=16000,
                verbose_name='Макс. вес пустого 27 л, г',
            ),
        ),
    ]
