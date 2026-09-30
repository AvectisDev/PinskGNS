from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('railway_service', '0004_railwaybatch_batch_type'),
    ]

    operations = [
        migrations.RenameField(
            model_name='railwaybatch',
            old_name='begin_date',
            new_name='started_at',
        ),
        migrations.RenameField(
            model_name='railwaybatch',
            old_name='end_date',
            new_name='completed_at',
        ),
        migrations.AlterModelOptions(
            name='railwaybatch',
            options={
                'ordering': ['-started_at'],
                'verbose_name': 'Партия приёмки жд цистерн',
                'verbose_name_plural': 'Партии приёмки жд цистерн',
            },
        ),
        migrations.AlterField(
            model_name='railwaybatch',
            name='started_at',
            field=models.DateTimeField(auto_now_add=True, verbose_name='Дата и время начала'),
        ),
        migrations.AlterField(
            model_name='railwaybatch',
            name='completed_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Дата и время окончания'),
        ),
    ]
