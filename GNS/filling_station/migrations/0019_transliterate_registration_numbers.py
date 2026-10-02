"""Транслитерация кириллических букв в registration_number → латиница."""

from collections import defaultdict

from django.db import migrations

# Дублируем map здесь: RunPython не должен импортировать код приложения.
_CYRILLIC_TO_LATIN = str.maketrans({
    'А': 'A', 'а': 'A',
    'В': 'B', 'в': 'B',
    'Е': 'E', 'е': 'E',
    'Ё': 'E', 'ё': 'E',
    'К': 'K', 'к': 'K',
    'М': 'M', 'м': 'M',
    'Н': 'H', 'н': 'H',
    'О': 'O', 'о': 'O',
    'Р': 'P', 'р': 'P',
    'С': 'C', 'с': 'C',
    'Т': 'T', 'т': 'T',
    'У': 'Y', 'у': 'Y',
    'Х': 'X', 'х': 'X',
})


def _to_storage(value: str) -> str:
    if not value:
        return value
    compact = ''.join(ch for ch in value.strip() if ch not in ' -')
    return compact.translate(_CYRILLIC_TO_LATIN).lower()


def _fk_weight_truck(apps, pk: int) -> int:
    Trailer = apps.get_model('filling_station', 'Trailer')
    BalloonsBatch = apps.get_model('filling_station', 'BalloonsBatch')
    AutoGasBatch = apps.get_model('autogas', 'AutoGasBatch')
    return (
        Trailer.objects.filter(truck_id=pk).count()
        + BalloonsBatch.objects.filter(truck_id=pk).count()
        + AutoGasBatch.objects.filter(truck_id=pk).count()
    )


def _merge_truck_into(apps, keeper_id: int, loser_id: int) -> None:
    Trailer = apps.get_model('filling_station', 'Trailer')
    BalloonsBatch = apps.get_model('filling_station', 'BalloonsBatch')
    AutoGasBatch = apps.get_model('autogas', 'AutoGasBatch')
    Truck = apps.get_model('filling_station', 'Truck')

    Trailer.objects.filter(truck_id=loser_id).update(truck_id=keeper_id)
    BalloonsBatch.objects.filter(truck_id=loser_id).update(truck_id=keeper_id)
    AutoGasBatch.objects.filter(truck_id=loser_id).update(truck_id=keeper_id)
    Truck.objects.filter(pk=loser_id).delete()


def transliterate_registration_numbers(apps, schema_editor):
    Truck = apps.get_model('filling_station', 'Truck')
    Trailer = apps.get_model('filling_station', 'Trailer')

    for model in (Truck, Trailer):
        groups = defaultdict(list)
        for obj in model.objects.all().iterator():
            key = _to_storage(obj.registration_number)
            if key:
                groups[key].append(obj)

        for storage_key, objects in groups.items():
            if len(objects) > 1 and model.__name__ == 'Truck':
                ranked = sorted(
                    objects,
                    key=lambda o: (_fk_weight_truck(apps, o.pk), -o.pk),
                    reverse=True,
                )
                keeper = ranked[0]
                for loser in ranked[1:]:
                    _merge_truck_into(apps, keeper.pk, loser.pk)
                objects = [keeper]

            elif len(objects) > 1:
                ids = ', '.join(str(o.pk) for o in objects)
                raise ValueError(
                    f'Коллизия после транслитерации: «{storage_key}» '
                    f'у {model.__name__} id={ids}'
                )

            obj = objects[0]
            obj.refresh_from_db()
            if obj.registration_number != storage_key:
                obj.registration_number = storage_key
                obj.save(update_fields=['registration_number'])


class Migration(migrations.Migration):

    dependencies = [
        ('filling_station', '0018_normalize_registration_numbers'),
        ('autogas', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(transliterate_registration_numbers, migrations.RunPython.noop),
    ]
