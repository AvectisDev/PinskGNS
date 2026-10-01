"""Публичный API сервисов filling_station (партии, RFID, Мириада, транспорт)."""

from filling_station.services.batches import (
    BATCH_CLOSE_WRITABLE_FIELDS,
    MIRIADA_BALLOON_STATUS_READERS,
    MIRIADA_BATCH_STATUS_READERS,
    MIRIADA_FILLING_READERS,
    OPEN_BATCH_STATUSES,
    add_balloon_to_batch_by_nfc,
    attempt_close_balloons_batch,
    pause_balloons_batch,
    pause_other_active_batches_on_reader,
    resume_balloons_batch,
    save_and_close_balloons_batch,
    send_batch_balloon_statuses_to_miriada,
    should_defer_balloon_status_to_batch_close,
    should_send_balloon_status_immediately,
)
from filling_station.services.miriada import (
    get_balloon_data_from_miriada,
    send_status_to_miriada,
)
from filling_station.services.rfid import (
    add_balloon_to_batch,
    add_balloon_to_cache,
    add_balloon_to_reader_table,
    add_sensor_count_to_batch,
    get_active_batch_for_reader,
    processing_request_with_nfc,
    processing_request_without_nfc,
    update_balloon_passport,
)
from filling_station.services.transport import (
    canonicalize_registration_number,
    find_transport_by_registration_number,
    format_trailer_hmi,
    format_truck_hmi,
    validate_trailer_input,
    validate_truck_input,
)

add_balloon_to_batch_with_miriada = add_balloon_to_batch_by_nfc

__all__ = [
    'BATCH_CLOSE_WRITABLE_FIELDS',
    'MIRIADA_BALLOON_STATUS_READERS',
    'MIRIADA_BATCH_STATUS_READERS',
    'MIRIADA_FILLING_READERS',
    'OPEN_BATCH_STATUSES',
    'add_balloon_to_batch',
    'add_balloon_to_batch_by_nfc',
    'add_balloon_to_batch_with_miriada',
    'add_balloon_to_cache',
    'add_balloon_to_reader_table',
    'add_sensor_count_to_batch',
    'attempt_close_balloons_batch',
    'canonicalize_registration_number',
    'find_transport_by_registration_number',
    'format_trailer_hmi',
    'format_truck_hmi',
    'get_active_batch_for_reader',
    'get_balloon_data_from_miriada',
    'pause_balloons_batch',
    'pause_other_active_batches_on_reader',
    'processing_request_with_nfc',
    'processing_request_without_nfc',
    'resume_balloons_batch',
    'save_and_close_balloons_batch',
    'send_batch_balloon_statuses_to_miriada',
    'send_status_to_miriada',
    'should_defer_balloon_status_to_batch_close',
    'should_send_balloon_status_immediately',
    'update_balloon_passport',
    'validate_trailer_input',
    'validate_truck_input',
]
