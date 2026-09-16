from __future__ import annotations

import logging

from django.core.cache import cache

logger = logging.getLogger('railway')

TANK_STATUS_LOG_CACHE_KEY = 'railway:last_logged_tank_status'


def log_railway_tank_status(opc_values: str) -> None:
    """Пишет снимок OPC цистерны в railway.log только при изменении."""
    if cache.get(TANK_STATUS_LOG_CACHE_KEY) == opc_values:
        return
    logger.info(opc_values)
    cache.set(TANK_STATUS_LOG_CACHE_KEY, opc_values, timeout=None)
