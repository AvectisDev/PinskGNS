"""Нормализация registration_number грузовиков и прицепов к storage-канону."""

from django.db import migrations


def _compact_lower(value: str) -> str:
    if not value:
        return value
    return ''.join(ch for ch in value.strip() if ch not in ' -').lower()


def normalize_registration_numbers(apps, schema_editor):
    Truck = apps.get_model('filling_station', 'Truck')
    Trailer = apps.get_model('filling_station', 'Trailer')

    for model in (Truck, Trailer):
        seen: dict[str, int] = {}
        for obj in model.objects.all().iterator():
            new_value = _compact_lower(obj.registration_number)
            if not new_value or new_value == obj.registration_number:
                if new_value:
                    if new_value in seen:
                        raise ValueError(
                            f'Коллизия registration_number после нормализации: '
                            f'«{new_value}» у {model.__name__} '
                            f'id={seen[new_value]} и id={obj.pk}'
                        )
                    seen[new_value] = obj.pk
                continue
            if new_value in seen:
                raise ValueError(
                    f'Коллизия registration_number после нормализации: '
                    f'«{new_value}» у {model.__name__} '
                    f'id={seen[new_value]} и id={obj.pk}'
                )
            seen[new_value] = obj.pk
            obj.registration_number = new_value
            obj.save(update_fields=['registration_number'])


class Migration(migrations.Migration):

    dependencies = [
        ('filling_station', '0017_truck_trailer_is_active'),
    ]

    operations = [
        migrations.RunPython(normalize_registration_numbers, migrations.RunPython.noop),
    ]
