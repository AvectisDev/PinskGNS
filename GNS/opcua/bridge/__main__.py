"""
Точка входа OPC UA bridge-процесса.

Запуск::

    python -m opcua.bridge

Или автоматически из GNS.asgi при старте Daphne.
"""

from __future__ import annotations

import asyncio
import logging
import logging.config
import os
import signal

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'GNS.settings')
django.setup()

from django.conf import settings  # noqa: E402

logging.config.dictConfig(settings.LOGGING)
logger = logging.getLogger('opcua')

from opcua.bridge.client import OpcBridgeClient  # noqa: E402
from opcua.bridge.dispatcher import TriggerDispatcher  # noqa: E402
from opcua.bridge.writer import run_write_loop  # noqa: E402


async def main() -> None:
    url = getattr(settings, 'OPC_SERVER_URL', '') or ''
    if not url:
        logger.error('OPC_SERVER_URL не задан — bridge не запущен')
        return

    dispatcher = TriggerDispatcher()
    bridge = OpcBridgeClient(url, dispatcher)
    stop_event = asyncio.Event()

    loop = asyncio.get_running_loop()

    def _request_stop() -> None:
        logger.info('OPC bridge: получен сигнал остановки')
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _request_stop)
        except NotImplementedError:
            # Windows: add_signal_handler ограничен
            signal.signal(sig, lambda *_: _request_stop())

    reconnect_delay = 2.0
    while not stop_event.is_set():
        try:
            await bridge.connect()
            reconnect_delay = 2.0
            write_task = asyncio.create_task(
                run_write_loop(bridge, stop_event),
                name='opcua-writer',
            )
            sub_task = asyncio.create_task(
                bridge.run_subscription_loop(),
                name='opcua-subscription',
            )
            stop_waiter = asyncio.create_task(stop_event.wait())

            done, pending = await asyncio.wait(
                {write_task, sub_task, stop_waiter},
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)

            for task in done:
                if task is stop_waiter:
                    break
                exc = task.exception() if not task.cancelled() else None
                if exc:
                    logger.error('OPC bridge task failed: %s', exc, exc_info=exc)

        except asyncio.CancelledError:
            break
        except Exception as error:
            logger.error('OPC bridge reconnect после ошибки: %s', error, exc_info=True)
        finally:
            await bridge.disconnect()

        if stop_event.is_set():
            break
        logger.info('OPC bridge переподключение через %.1f с', reconnect_delay)
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=reconnect_delay)
            break
        except asyncio.TimeoutError:
            reconnect_delay = min(reconnect_delay * 1.5, 30.0)

    logger.info('OPC bridge остановлен')


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
