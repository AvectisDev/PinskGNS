"""Обратная совместимость: нормализация номеров перенесена в transport.registration."""

from transport.registration import (  # noqa: F401
    TRAILER_INPUT_HELP,
    TRUCK_INPUT_HELP,
    canonicalize_registration_number,
    compact_registration_number,
    find_transport_by_registration_number,
    format_trailer_hmi,
    format_truck_hmi,
    validate_trailer_input,
    validate_truck_input,
)
