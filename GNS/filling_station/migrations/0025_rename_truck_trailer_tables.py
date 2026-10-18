from django.db import migrations


class Migration(migrations.Migration):
    """Переименовывает таблицы грузовиков/прицепов в transport_*."""

    dependencies = [
        ('filling_station', '0024_balloon_miriada_status_error'),
    ]

    operations = [
        migrations.AlterModelTable(
            name='trucktype',
            table='transport_trucktype',
        ),
        migrations.AlterModelTable(
            name='truck',
            table='transport_truck',
        ),
        migrations.AlterModelTable(
            name='trailertype',
            table='transport_trailertype',
        ),
        migrations.AlterModelTable(
            name='trailer',
            table='transport_trailer',
        ),
    ]
