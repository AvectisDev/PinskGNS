# Generated by Django 5.0.6 on 2024-10-22 09:30

import pgtrigger.compiler
import pgtrigger.migrations
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('filling_station', '0041_alter_balloon_size'),
    ]

    operations = [
        pgtrigger.migrations.RemoveTrigger(
            model_name='balloon',
            name='insert_insert',
        ),
        pgtrigger.migrations.RemoveTrigger(
            model_name='balloon',
            name='update_update',
        ),
        migrations.AddField(
            model_name='balloonevent',
            name='size',
            field=models.IntegerField(choices=[(5, 5), (12, 12), (27, 27), (50, 50)], default=50, verbose_name='Объём'),
        ),
        migrations.AlterField(
            model_name='balloon',
            name='nfc_tag',
            field=models.CharField(blank=True, max_length=30, null=True, verbose_name='Номер метки'),
        ),
        migrations.AlterField(
            model_name='balloonevent',
            name='nfc_tag',
            field=models.CharField(blank=True, max_length=30, null=True, verbose_name='Номер метки'),
        ),
        pgtrigger.migrations.AddTrigger(
            model_name='balloon',
            trigger=pgtrigger.compiler.Trigger(name='insert_insert', sql=pgtrigger.compiler.UpsertTriggerSql(func='INSERT INTO "filling_station_balloonevent" ("brutto", "creation_date", "current_examination_date", "id", "manufacturer", "netto", "next_examination_date", "nfc_tag", "pgh_context_id", "pgh_created_at", "pgh_label", "pgh_obj_id", "serial_number", "size", "status", "user_id", "wall_thickness") VALUES (NEW."brutto", NEW."creation_date", NEW."current_examination_date", NEW."id", NEW."manufacturer", NEW."netto", NEW."next_examination_date", NEW."nfc_tag", _pgh_attach_context(), NOW(), \'insert\', NEW."id", NEW."serial_number", NEW."size", NEW."status", NEW."user_id", NEW."wall_thickness"); RETURN NULL;', hash='646dcff392a42cad53fc6d083e590bf3a6d1a9d7', operation='INSERT', pgid='pgtrigger_insert_insert_703b2', table='filling_station_balloon', when='AFTER')),
        ),
        pgtrigger.migrations.AddTrigger(
            model_name='balloon',
            trigger=pgtrigger.compiler.Trigger(name='update_update', sql=pgtrigger.compiler.UpsertTriggerSql(condition='WHEN (OLD."brutto" IS DISTINCT FROM (NEW."brutto") OR OLD."creation_date" IS DISTINCT FROM (NEW."creation_date") OR OLD."current_examination_date" IS DISTINCT FROM (NEW."current_examination_date") OR OLD."id" IS DISTINCT FROM (NEW."id") OR OLD."manufacturer" IS DISTINCT FROM (NEW."manufacturer") OR OLD."netto" IS DISTINCT FROM (NEW."netto") OR OLD."next_examination_date" IS DISTINCT FROM (NEW."next_examination_date") OR OLD."nfc_tag" IS DISTINCT FROM (NEW."nfc_tag") OR OLD."serial_number" IS DISTINCT FROM (NEW."serial_number") OR OLD."size" IS DISTINCT FROM (NEW."size") OR OLD."status" IS DISTINCT FROM (NEW."status") OR OLD."user_id" IS DISTINCT FROM (NEW."user_id") OR OLD."wall_thickness" IS DISTINCT FROM (NEW."wall_thickness"))', func='INSERT INTO "filling_station_balloonevent" ("brutto", "creation_date", "current_examination_date", "id", "manufacturer", "netto", "next_examination_date", "nfc_tag", "pgh_context_id", "pgh_created_at", "pgh_label", "pgh_obj_id", "serial_number", "size", "status", "user_id", "wall_thickness") VALUES (NEW."brutto", NEW."creation_date", NEW."current_examination_date", NEW."id", NEW."manufacturer", NEW."netto", NEW."next_examination_date", NEW."nfc_tag", _pgh_attach_context(), NOW(), \'update\', NEW."id", NEW."serial_number", NEW."size", NEW."status", NEW."user_id", NEW."wall_thickness"); RETURN NULL;', hash='a396e8d8e187cd998233e66dc9e3ecdfd1117939', operation='UPDATE', pgid='pgtrigger_update_update_08342', table='filling_station_balloon', when='AFTER')),
        ),
    ]
