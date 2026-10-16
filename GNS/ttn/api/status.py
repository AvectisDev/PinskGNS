"""Сопоставление статуса MiriadaTtn для мобильного API (int) и БД (str)."""

from ttn.models import MiriadaTtnStatus

STATUS_TO_API = {
    MiriadaTtnStatus.NOT_PROCESSED: 1,
    MiriadaTtnStatus.ERROR: 2,
    MiriadaTtnStatus.CLOSED: 3,
}


def miriada_ttn_status_to_api(status: str | None) -> int:
    """
    Преобразует строковый статус БД в числовой enum API.

    Args:
        status: статус ТТН в БД.

    Returns:
        int: 1–3 или 0 при неизвестном значении.
    """
    return STATUS_TO_API.get(status, 0)
