import django
from django.core.management import call_command
from django.db import connection
from autogas.models import AutoGasBatch, Truck, Trailer, User  # Модели из autogas
from filling_station.models import AutoGasBatch as FillingStationAutoGasBatch  # Модель из filling_station

# Убедитесь, что у вас активирован правильный проект и приложение
django.setup()


def migrate_data():
    print("Начинаем миграцию данных...")

    filling_station_objects = FillingStationAutoGasBatch.objects.all()

    for obj in filling_station_objects:
        new_obj = AutoGasBatch.objects.create(
            batch_type=obj.batch_type,
            # пропустить begin_date и begin_time при создании
            end_date=obj.end_date,
            end_time=obj.end_time,
            truck=Truck.objects.get(id=obj.truck_id),
            trailer=Trailer.objects.get(id=obj.trailer_id) if obj.trailer_id else None,
            gas_amount=obj.gas_amount,
            gas_type=obj.gas_type,
            scale_empty_weight=obj.scale_empty_weight,
            scale_full_weight=obj.scale_full_weight,
            weight_gas_amount=obj.weight_gas_amount,
            is_active=obj.is_active,
            user=User.objects.get(id=obj.user_id)
        )

        # Обновляем поля даты и времени без повторного сохранения объекта
        AutoGasBatch.objects.filter(id=new_obj.id).update(
            begin_date=obj.begin_date,
            begin_time=obj.begin_time
        )

        print(f"Мигрирована запись {obj.id}")

    print("Миграция данных завершена!")


# Запустите функцию migrate_data
migrate_data()
