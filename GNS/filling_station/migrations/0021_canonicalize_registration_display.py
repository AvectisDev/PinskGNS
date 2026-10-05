"""Приведение registration_number к канону display: AI 0008-1 / A 3779B-1."""

import re
from collections import defaultdict

from django.db import migrations

_TRUCK_COMPACT = re.compile(r'^([A-Za-z]{2})(\d{4})(\d)$')
_TRAILER_COMPACT = re.compile(r'^([A-Za-z])(\d{4})([A-Za-z])(\d)$')


def _canonicalize(value: str) -> str:
    if not value:
        return value
    original = value.strip()
    compact = ''.join(ch for ch in original if ch not in ' -')
    if not compact:
        return original
    truck = _TRUCK_COMPACT.match(compact)
    if truck:
        letters, digits, region = truck.groups()
        return f'{letters.upper()} {digits}-{region}'
    trailer = _TRAILER_COMPACT.match(compact)
    if trailer:
        letter, digits, middle, region = trailer.groups()
        return f'{letter.upper()} {digits}{middle.upper()}-{region}'
    return original


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


def canonicalize_registration_numbers(apps, schema_editor):
    Truck = apps.get_model('filling_station', 'Truck')
    Trailer = apps.get_model('filling_station', 'Trailer')

    for model in (Truck, Trailer):
        groups = defaultdict(list)
        for obj in model.objects.all().iterator():
            key = _canonicalize(obj.registration_number)
            if key:
                groups[key].append(obj)

        for canonical, objects in groups.items():
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
                    f'Коллизия после canonicalize: «{canonical}» '
                    f'у {model.__name__} id={ids}'
                )

            obj = objects[0]
            obj.refresh_from_db()
            if obj.registration_number != canonical:
                obj.registration_number = canonical
                obj.save(update_fields=['registration_number'])


class Migration(migrations.Migration):

    dependencies = [
        ('filling_station', '0020_remove_placeholder_trailer'),
        ('autogas', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(canonicalize_registration_numbers, migrations.RunPython.noop),
    ]
