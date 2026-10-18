"""Форматирование вариантов выбора грузовиков и прицепов в формах."""

from django.db.models import Q

from transport.models import Driver, Trailer, Truck


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


def available_drivers_queryset(truck=None):
    """
    Активные водители, не занятые другим грузовиком.

    Текущий водитель переданного грузовика остаётся в списке,
    даже если он уже помечен неактивным.
    """
    queryset = Driver.objects.filter(is_active=True, truck__isnull=True)
    if truck is not None and truck.pk and truck.driver_id:
        queryset = Driver.objects.filter(
            Q(pk=truck.driver_id) | Q(is_active=True, truck__isnull=True)
        )
    return queryset.order_by('last_name', 'first_name')


def configure_driver_field(field, truck=None):
    """Настраивает ModelChoiceField для выбора водителя у грузовика."""
    field.queryset = available_drivers_queryset(truck)
    field.empty_label = 'Не выбран'
    field.required = False


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
