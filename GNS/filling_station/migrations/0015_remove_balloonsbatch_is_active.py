from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('filling_station', '0014_balloonsbatch_status'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='balloonsbatch',
            name='is_active',
        ),
    ]
