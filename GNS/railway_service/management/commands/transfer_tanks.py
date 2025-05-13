from django.core.management.base import BaseCommand
from filling_station.models import RailwayTank as OldRailwayTank
from railway_service.models import RailwayTank as NewRailwayTank
from django.contrib.auth.models import User


class Command(BaseCommand):
    help = 'Transfer RailwayTank records with original IDs'

    def handle(self, *args, **options):
        # Сначала удаляем все существующие записи в новой модели (если нужно)
        NewRailwayTank.objects.all().delete()

        for old_tank in OldRailwayTank.objects.all():
            user = User.objects.get(pk=old_tank.user_id) if User.objects.filter(
                pk=old_tank.user_id).exists() else User.objects.get(pk=1)

            # Создаем объект с сохранением оригинального ID
            new_tank = NewRailwayTank(
                id=old_tank.id,  # Сохраняем оригинальный ID
                registration_number=old_tank.registration_number,
                empty_weight=old_tank.empty_weight,
                full_weight=old_tank.full_weight,
                gas_weight=old_tank.gas_weight,
                gas_type=old_tank.gas_type,
                is_on_station=old_tank.is_on_station,
                railway_ttn=old_tank.railway_ttn,
                netto_weight_ttn=old_tank.netto_weight_ttn,
                entry_date=old_tank.entry_date,
                entry_time=old_tank.entry_time,
                departure_date=old_tank.departure_date,
                departure_time=old_tank.departure_time,
                registration_number_img=old_tank.registration_number_img,
                user=user
            )
            new_tank.save(force_insert=True)  # force_insert гарантирует вставку, а не обновление

        self.stdout.write(self.style.SUCCESS(
            f'Successfully transferred {OldRailwayTank.objects.count()} records with original IDs'
        ))