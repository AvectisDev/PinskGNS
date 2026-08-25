from django.db import migrations, models


def migrate_batch_status(apps, schema_editor):
    BalloonsBatch = apps.get_model('filling_station', 'BalloonsBatch')
    for batch in BalloonsBatch.objects.all().iterator():
        if batch.is_active:
            batch.status = 'active'
        elif batch.miriada_close_failed:
            batch.status = 'miriada_error'
        elif batch.completed_at:
            batch.status = 'completed'
        else:
            batch.status = 'paused'
        batch.save(update_fields=['status'])


class Migration(migrations.Migration):

    dependencies = [
        ('filling_station', '0013_balloonsbatch_amount_of_ttn_and_miriada_balloons_sent'),
    ]

    operations = [
        migrations.AddField(
            model_name='balloonsbatch',
            name='status',
            field=models.CharField(
                choices=[
                    ('active', 'В работе'),
                    ('paused', 'Приостановлена'),
                    ('completed', 'Завершена'),
                    ('miriada_error', 'Завершена, ошибка Мириады'),
                ],
                db_index=True,
                default='paused',
                max_length=20,
                verbose_name='Статус партии',
            ),
        ),
        migrations.RunPython(migrate_batch_status, migrations.RunPython.noop),
    ]
