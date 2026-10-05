from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('filling_station', '0021_canonicalize_registration_display'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='balloonsbatch',
            name='amount_of_rfid',
        ),
    ]
