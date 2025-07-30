from django.core.management.base import BaseCommand
from django.db import transaction
from autogas.models import AutoGasBatch
from filling_station.models import AutoGasBatch as OldAutoGasBatch
from ttn.models import AutoTtn


class Command(BaseCommand):
    help = 'Сопоставляет партии по полям и обновляет batch_id в AutoTtn на новые ID из autogas_autogasbatch'

    def handle(self, *args, **options):
        self.stdout.write("🔄 Начинаем сопоставление партий и обновление batch_id в AutoTtn...")

        updated_count = 0
        unmatched_count = 0

        with transaction.atomic():
            for ttn in AutoTtn.objects.exclude(batch=None):
                old_batch = OldAutoGasBatch.objects.filter(id=ttn.batch_id).first()
                if not old_batch:
                    continue

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
                    ttn.batch = matched
                    ttn.save()
                    updated_count += 1
                else:
                    unmatched_count += 1

        self.stdout.write(f"✅ Обновлено записей ТТН: {updated_count}")
        self.stdout.write(f"⚠️ Не удалось сопоставить: {unmatched_count}")
