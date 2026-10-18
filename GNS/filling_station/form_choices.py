"""Обратная совместимость: подписи выбора транспорта в transport.form_choices."""

from transport.form_choices import (  # noqa: F401
    configure_trailer_field,
    configure_truck_field,
    format_trailer_choice,
    format_truck_choice,
)
