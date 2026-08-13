from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ttn', '0008_alter_autottn_gas_type_alter_railwayttn_gas_type'),
    ]

    operations = [
        migrations.AlterField(
            model_name='autottn',
            name='date',
            field=models.DateTimeField(auto_now_add=True, verbose_name='Дата формирования накладной'),
        ),
        migrations.AlterField(
            model_name='balloonttn',
            name='date',
            field=models.DateTimeField(auto_now_add=True, verbose_name='Дата формирования накладной'),
        ),
        migrations.AlterField(
            model_name='railwayttn',
            name='date',
            field=models.DateTimeField(auto_now_add=True, verbose_name='Дата формирования накладной'),
        ),
    ]
