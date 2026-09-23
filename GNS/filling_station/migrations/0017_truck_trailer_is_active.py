# Generated manually for Truck/Trailer.is_active

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('filling_station', '0016_alter_do_nothing_to_protect'),
    ]

    operations = [
        migrations.AddField(
            model_name='truck',
            name='is_active',
            field=models.BooleanField(default=True, verbose_name='Активен'),
        ),
        migrations.AddField(
            model_name='trailer',
            name='is_active',
            field=models.BooleanField(default=True, verbose_name='Активен'),
        ),
    ]
