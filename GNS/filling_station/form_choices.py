"""Форматирование вариантов выбора грузовиков и прицепов в формах."""

from .models import Truck, Trailer


def format_truck_choice(truck: Truck) -> str:
    """Подпись грузовика в выпадающем списке: номер, марка, тип."""
    return (
        f'{truck.registration_number} | '
        f'Марка: {truck.car_brand or "---"} | '
        f'Тип: {truck.type}'
    )


def format_trailer_choice(trailer: Trailer) -> str:
    """Подпись прицепа в выпадающем списке: номер, марка, тип."""
    return (
        f'{trailer.registration_number} | '
        f'Марка: {trailer.trailer_brand or "---"} | '
        f'Тип: {trailer.type}'
    )


def configure_truck_field(field, queryset=None):
    """Настраивает ModelChoiceField для выбора грузовика."""
    qs = queryset if queryset is not None else field.queryset
    field.queryset = qs.select_related('type')
    field.label_from_instance = format_truck_choice


def configure_trailer_field(field, queryset=None):
    """Настраивает ModelChoiceField для выбора прицепа."""
    qs = queryset if queryset is not None else field.queryset
    field.queryset = qs.select_related('type')
    field.label_from_instance = format_trailer_choice
