"""Сопоставление статуса партии для мобильного API (int) и БД (str)."""

from filling_station.models import BatchStatus

STATUS_TO_API = {
    BatchStatus.ACTIVE: 1,
    BatchStatus.PAUSED: 2,
    BatchStatus.COMPLETED: 3,
    BatchStatus.MIRIADA_ERROR: 4,
}

STATUS_FROM_API = {api: db for db, api in STATUS_TO_API.items()}


def batch_status_to_api(status: str | None) -> int:
    return STATUS_TO_API.get(status, 0)


def batch_status_from_api(value) -> str:
    try:
        api_value = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f'Некорректный статус партии: {value}') from exc
    if api_value not in STATUS_FROM_API:
        raise ValueError(f'Некорректный статус партии: {value}')
    return STATUS_FROM_API[api_value]


def is_api_close_request(data: dict) -> bool:
    """True, если в теле PATCH передан status=3 (COMPLETED)."""
    if 'status' not in data:
        return False
    try:
        return batch_status_from_api(data['status']) == BatchStatus.COMPLETED
    except ValueError:
        return False
