import os
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import datetime
from filling_station.models import BalloonsUnloadingBatch, BalloonsLoadingBatch, AutoGasBatch
from railway_service.models import RailwayBatch
from ttn.models import FilePath


class Command(BaseCommand):
    help = 'Generate 1C file'
    today = timezone.now().strftime('%d.%m.%y')
    # day_for_search = timezone.now()
    day_for_search = datetime(2025, 4, 22)     # для тестирования

    def handle(self, *args, **kwargs):
        filename = f'ГНС{self.today}.txt'
        file_path = FilePath.objects.first()
        path = file_path.path if file_path and file_path.path else None

        content_1 = self.generate_railway_list()
        content_2 = self.generate_loading_auto_gas_list()
        content_3 = self.generate_unloading_auto_gas_list()
        content_4 = self.generate_balloon_loading_list()
        content_5 = self.generate_balloon_unloading_list()

        content = '\n'.join([content_1, content_2, content_3, content_4, content_5])

        if path:
            full_path = os.path.join(path, filename)
            with open(full_path, 'w', encoding='windows-1251') as file:
                file.write(content)
        else:
            # Логика для обмена по API
            pass

    def generate_railway_list(self):
        lines = ['ГНС-ТТН1']

        try:
            batches = RailwayBatch.objects.filter(begin_date__date=self.day_for_search)

            if not batches.exists():
                return '\n'.join(lines)

            for batch in batches:
                ttns = batch.railwayttn_set.all()

                if not ttns.exists():
                    continue  # Пропускаем партии без TTN

                for ttn in ttns:
                    # Получаем цистерны - сначала из TTN, если нет, то из партии
                    railway_tanks = ttn.railway_tank_list.all() or batch.railway_tank_list.all()

                    if not railway_tanks.exists():
                        continue  # Пропускаем TTN без цистерн

                    # Добавляем строку с данными TTN
                    lines.append(
                        f'{ttn.number};'
                        f'{ttn.date.strftime("%d.%m.%y") if ttn.date else ""};'
                        f'{batch.begin_date.strftime("%d.%m.%y")};'
                        f'{ttn.shipper.name if ttn.shipper else ""};'
                    )

                    # Добавляем строки для каждой цистерны
                    for tank in railway_tanks:
                        lines.append(
                            f'{tank.registration_number};'
                            f'{ttn.gas_type};'
                            f'{ttn.total_gas_amount_by_ttn or 0};'
                            f'{tank.gas_weight or 0};'
                            f'{tank.departure_date.strftime("%d.%m.%y") if tank.departure_date else ""};'
                            f'{ttn.railway_ttn or ""};'
                        )

        except Exception as e:
            print(f"Ошибка при генерации списка жд цистерн: {str(e)}")

        return '\n'.join(lines)

    def generate_loading_auto_gas_list(self):
        batches = AutoGasBatch.objects.filter(batch_type='l', begin_date=self.day_for_search)

        lines = ['ГНС-ТТН2']
        print(lines, batches)

        if batches:
            for batch in batches:
                try:
                    ttn = batch.auto_batch_for_ttn.first()
                    if not ttn:
                        continue

                    lines.append(f'{ttn.number};'
                                 f'{ttn.date.strftime("%d.%m.%y") if ttn.date else ""};'
                                 f'{ttn.shipper.name if ttn.shipper else ""};'
                                 f'{batch.weight_gas_amount or 0};'
                                 f'{batch.gas_amount or 0};'
                                 f'{batch.truck.registration_number if batch.truck else ""};')
                except Exception as e:
                    print(f"Error processing batch {batch.id}: {str(e)}")
                    continue

        return '\n'.join(lines)

    def generate_unloading_auto_gas_list(self):
        batches = AutoGasBatch.objects.filter(batch_type='u', begin_date=self.day_for_search)

        lines = ['ГНС-ТТН3']
        print(lines, batches)

        if batches:
            for batch in batches:
                try:
                    ttn = batch.auto_batch_for_ttn.first()
                    print(lines, batches, ttn)
                    if not ttn:
                        continue

                    lines.append(f'{ttn.number};'
                                 f'{ttn.date.strftime("%d.%m.%y") if ttn.date else ""};'
                                 f'{ttn.shipper.name if ttn.shipper else ""};'
                                 f'{batch.weight_gas_amount or 0};'
                                 f'{batch.gas_amount or 0};'
                                 f'{batch.truck.registration_number if batch.truck else ""};')
                except Exception as e:
                    print(f"Error processing batch {batch.id}: {str(e)}")
                    continue

        return '\n'.join(lines)

    def generate_balloon_loading_list(self):
        batches = BalloonsLoadingBatch.objects.filter(begin_date=self.day_for_search)

        lines = ['ГНС-ТТН4']

        if batches:
            for batch in batches:
                try:
                    ttn = batch.ttn_loading.first()
                    if not ttn:
                        continue

                    lines.append(f'{ttn.number};'
                                 f'{ttn.date.strftime("%d.%m.%y") if ttn.date else ""};'
                                 f'{ttn.shipper.name if ttn.shipper else ""};'
                                 f'{batch.truck.registration_number if batch.truck else ""};')

                    lines.append(f';'
                                 f'Баллоны 50 л;'
                                 f'{(batch.amount_of_rfid or 0) + (batch.amount_of_50_liters or 0)};'
                                 f'0;'
                                 f'0;')
                    lines.append(f';'
                                 f'Баллоны 27 л;'
                                 f'{batch.amount_of_27_liters or 0};'
                                 f'0;'
                                 f'0;')
                    lines.append(f';'
                                 f'Баллоны 12 л;'
                                 f'{batch.amount_of_12_liters or 0};'
                                 f'0;'
                                 f'0;')
                    lines.append(f';'
                                 f'Баллоны 5 л;'
                                 f'{batch.amount_of_5_liters or 0};'
                                 f'0;'
                                 f'0;')
                except Exception as e:
                    print(f"Error processing loading batch {batch.id}: {str(e)}")
                    continue

        return '\n'.join(lines)

    def generate_balloon_unloading_list(self):
        batches = BalloonsUnloadingBatch.objects.filter(begin_date=self.day_for_search)

        lines = ['ГНС-ТТН5']

        if batches:
            for batch in batches:
                try:
                    ttn = batch.ttn_unloading.first()
                    if not ttn:
                        continue

                    lines.append(f'{ttn.number};'
                                 f'{ttn.date.strftime("%d.%m.%y") if ttn.date else ""};'
                                 f'{ttn.shipper.name if ttn.shipper else ""};'
                                 f'{batch.truck.registration_number if batch.truck else ""};')

                    balloons = batch.balloon_list.all()
                    total_gas_weight = 0
                    total_balloon_weight = 0
                    if balloons:
                        for balloon in balloons:
                            total_gas_weight += (balloon.brutto or 0) - (balloon.netto or 0)
                            total_balloon_weight += (balloon.brutto or 0)

                    lines.append(f'СПБТ;'
                                 f'Баллоны 50 л;'
                                 f'{(batch.amount_of_rfid or 0) + (batch.amount_of_50_liters or 0)};'
                                 f'{total_gas_weight};'
                                 f'{total_balloon_weight};')
                    lines.append(f'СПБТ;'
                                 f'Баллоны 27 л;'
                                 f'{batch.amount_of_27_liters or 0};'
                                 f'0;'
                                 f'0;')
                    lines.append(f'СПБТ;'
                                 f'Баллоны 12 л;'
                                 f'{batch.amount_of_12_liters or 0};'
                                 f'0;'
                                 f'0;')
                    lines.append(f'СПБТ;'
                                 f'Баллоны 5 л;'
                                 f'{batch.amount_of_5_liters or 0};'
                                 f'0;'
                                 f'0;')
                except Exception as e:
                    print(f"Error processing unloading batch {batch.id}: {str(e)}")
                    continue

        return '\n'.join(lines)
