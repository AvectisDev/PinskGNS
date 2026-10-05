"""Consumer Redis write-queue → asyncua write с ретраями."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from opcua import api as opc_api

if TYPE_CHECKING:
    from opcua.bridge.client import OpcBridgeClient

logger = logging.getLogger('opcua')

WRITE_MAX_ATTEMPTS = 3
WRITE_RETRY_DELAY_SECONDS = 0.5


async def _write_with_retries(
    bridge: OpcBridgeClient,
    name: str,
    value: Any,
) -> None:
    """Пишет тег в OPC; при ошибке повторяет с паузой."""
    last_error: BaseException | None = None
    for attempt in range(1, WRITE_MAX_ATTEMPTS + 1):
        try:
            await bridge.write_tag(name, value)
            if attempt > 1:
                logger.info(
                    'OPC write %s=%s успешен с попытки %s',
                    name,
                    value,
                    attempt,
                )
            return
        except Exception as error:
            last_error = error
            logger.warning(
                'OPC write failed %s=%s (попытка %s/%s): %s',
                name,
                value,
                attempt,
                WRITE_MAX_ATTEMPTS,
                error,
            )
            if attempt < WRITE_MAX_ATTEMPTS:
                await asyncio.sleep(WRITE_RETRY_DELAY_SECONDS * attempt)

    assert last_error is not None
    logger.error(
        'OPC write abandoned %s=%s после %s попыток: %s',
        name,
        value,
        WRITE_MAX_ATTEMPTS,
        last_error,
        exc_info=last_error,
    )
    raise last_error


async def run_write_loop(bridge: OpcBridgeClient, stop_event: asyncio.Event) -> None:
    """Читает запросы записи из Redis и выполняет их в OPC-сессии bridge."""
    while not stop_event.is_set():
        try:
            request = await asyncio.to_thread(
                opc_api.pop_write_request,
                opc_api.WRITE_POLL_TIMEOUT,
            )
        except Exception as error:
            logger.error('OPC write queue error: %s', error, exc_info=True)
            await asyncio.sleep(1)
            continue

        if request is None:
            continue

        name = request.get('name', '')
        value = request.get('value')
        try:
            await _write_with_retries(bridge, name, value)
        except Exception:
            # Уже залогировано в _write_with_retries; сообщение из Redis снято,
            # повторная постановка — ответственность домена при следующем событии.
            continue
