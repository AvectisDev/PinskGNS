"""Нормализация registration_number грузовиков и прицепов к storage-канону."""

from collections import defaultdict

from django.db import migrations


def _compact_lower(value: str) -> str:
    if not value:
        return value
    return ''.join(ch for ch in value.strip() if ch not in ' -').lower()


def _fk_weight(model_name: str, pk: int, apps) -> int:
    """Сколько связанных записей держит Truck/Trailer — для выбора «главного» дубликата."""
    if model_name == 'Truck':
        Trailer = apps.get_model('filling_station', 'Trailer')
        BalloonsBatch = apps.get_model('filling_station', 'BalloonsBatch')
        AutoGasBatch = apps.get_model('autogas', 'AutoGasBatch')
        return (
            Trailer.objects.filter(truck_id=pk).count()
            + BalloonsBatch.objects.filter(truck_id=pk).count()
            + AutoGasBatch.objects.filter(truck_id=pk).count()
        )
    return 0


def _merge_truck_into(apps, keeper_id: int, loser_id: int) -> None:
    Trailer = apps.get_model('filling_station', 'Trailer')
    BalloonsBatch = apps.get_model('filling_station', 'BalloonsBatch')
    AutoGasBatch = apps.get_model('autogas', 'AutoGasBatch')
    Truck = apps.get_model('filling_station', 'Truck')

    Trailer.objects.filter(truck_id=loser_id).update(truck_id=keeper_id)
    BalloonsBatch.objects.filter(truck_id=loser_id).update(truck_id=keeper_id)
    AutoGasBatch.objects.filter(truck_id=loser_id).update(truck_id=keeper_id)
    Truck.objects.filter(pk=loser_id).delete()


def normalize_registration_numbers(apps, schema_editor):
    Truck = apps.get_model('filling_station', 'Truck')
    Trailer = apps.get_model('filling_station', 'Trailer')

    for model in (Truck, Trailer):
        groups: dict[str, list] = defaultdict(list)
        for obj in model.objects.all().iterator():
            key = _compact_lower(obj.registration_number)
            if key:
                groups[key].append(obj)

        for storage_key, objects in groups.items():
            if len(objects) == 1:
                obj = objects[0]
                if obj.registration_number != storage_key:
                    obj.registration_number = storage_key
                    obj.save(update_fields=['registration_number'])
                continue

            # Дубликаты одного номера после compact+lower.
            if model.__name__ != 'Truck':
                ids = ', '.join(str(o.pk) for o in objects)
                raise ValueError(
                    f'Коллизия registration_number после нормализации: '
                    f'«{storage_key}» у Trailer id={ids}. '
                    f'Слияние для прицепов не реализовано — разберите вручную.'
                )

            ranked = sorted(
                objects,
                key=lambda o: (_fk_weight('Truck', o.pk, apps), -o.pk),
                reverse=True,
            )
            keeper = ranked[0]
            for loser in ranked[1:]:
                _merge_truck_into(apps, keeper.pk, loser.pk)

            keeper.refresh_from_db()
            if keeper.registration_number != storage_key:
                keeper.registration_number = storage_key
                keeper.save(update_fields=['registration_number'])


class Migration(migrations.Migration):

    dependencies = [
        ('filling_station', '0017_truck_trailer_is_active'),
        ('autogas', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(normalize_registration_numbers, migrations.RunPython.noop),
    ]
