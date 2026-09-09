# Make number required and unique

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('carousel', '0005_populate_carouselsettings_instance_fields'),
    ]

    operations = [
        migrations.AlterField(
            model_name='carouselsettings',
            name='number',
            field=models.IntegerField(
                unique=True,
                verbose_name='Номер карусели',
            ),
        ),
    ]
