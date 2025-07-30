from django.core.management.base import BaseCommand
from django.db import connection
from autogas.models import AutoGasBatch
from filling_station.models import AutoGasBatch as OldAutoGasBatch
from ttn.models import AutoTtn


class Command(BaseCommand):
    help = 'Migrate batch_id references from filling_station_autogasbatch to autogas_autogasbatch in AutoTtn records.'

    def handle(self, *args, **options):
        self.stdout.write("Начинаем миграцию batch_id для AutoTtn...")

        # Создаем отображение: старый id -> новый id
        mapping = {}

        for old_batch in OldAutoGasBatch.objects.all():
            matched = AutoGasBatch.objects.filter(
                batch_type=old_batch.batch_type,
                begin_date=old_batch.begin_date,
                begin_time=old_batch.begin_time,
                truck_id=old_batch.truck_id,
                trailer_id=old_batch.trailer_id,
                gas_amount=old_batch.gas_amount,
                gas_type=old_batch.gas_type,
                scale_empty_weight=old_batch.scale_empty_weight,
                scale_full_weight=old_batch.scale_full_weight,
                weight_gas_amount=old_batch.weight_gas_amount,
                user_id=old_batch.user_id
            ).first()

            if matched:
                mapping[old_batch.id] = matched.id

        # Временно отключаем проверку внешних ключей
        with connection.cursor() as cursor:
            cursor.execute("SET CONSTRAINTS ALL DEFERRED")

        # Обновим batch_id в AutoTtn
        updated_count = 0
        for ttn in AutoTtn.objects.all():
            old_id = ttn.batch_id
            new_id = mapping.get(old_id)
            if new_id:
                ttn.batch_id = new_id
                ttn.save()
                updated_count += 1

        # Включаем проверку внешних ключей обратно
        with connection.cursor() as cursor:
            cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")

        self.stdout.write(f"Обновлено записей ТТН: {updated_count}")
        self.stdout.write("Миграция завершена успешно.")