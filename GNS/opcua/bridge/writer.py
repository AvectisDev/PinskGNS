"""Consumer Redis write-queue → asyncua write."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from opcua import api as opc_api

if TYPE_CHECKING:
    from opcua.bridge.client import OpcBridgeClient

logger = logging.getLogger('opcua')


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

        request_id = request.get('id', '')
        name = request.get('name', '')
        value = request.get('value')
        try:
            await bridge.write_tag(name, value)
            opc_api.publish_write_result(request_id, 'ok')
        except Exception as error:
            logger.error(
                'OPC write failed %s=%s: %s',
                name,
                value,
                error,
                exc_info=True,
            )
            if request_id:
                opc_api.publish_write_result(request_id, f'error:{error}')
