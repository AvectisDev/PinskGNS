from __future__ import annotations

import logging
import threading
from typing import Any

from opcua import Client

logger = logging.getLogger('celery')

OPC_TIMEOUT_SECONDS = 2.0


def create_opc_client(url: str, timeout: float = OPC_TIMEOUT_SECONDS) -> Client:
    """Создаёт OPC UA клиент с таймаутом сокета и запросов."""
    return Client(url, timeout=timeout)


def disconnect_opc(
    client: Client,
    timeout: float = OPC_TIMEOUT_SECONDS,
) -> None:
    """
    Закрывает OPC-сессию с ограничением по времени.
    На Windows disconnect() python-opcua может ждать receive-поток бесконечно.
    """
    error: list[BaseException] = []

    def _disconnect() -> None:
        try:
            client.disconnect()
        except Exception as exc:
            error.append(exc)

    thread = threading.Thread(
        target=_disconnect,
        daemon=True,
        name='opc-disconnect',
    )
    thread.start()
    thread.join(timeout)

    if thread.is_alive():
        logger.warning(
            'OPC disconnect превысил %.1f с, принудительно закрываю сокет',
            timeout,
        )
        _force_close_socket(client)
        thread.join(timeout)
        return

    if error:
        logger.warning('Ошибка OPC disconnect: %s', error[0])


def _force_close_socket(client: Client) -> None:
    sockets: list[Any] = []
    uaclient = getattr(client, 'uaclient', None)
    socket_client = getattr(uaclient, '_socket', None)
    if socket_client is None:
        return

    sockets.append(socket_client)
    inner = getattr(socket_client, '_socket', None)
    if inner is not None:
        sockets.append(inner)
        raw_socket = getattr(inner, 'socket', None)
        if raw_socket is not None:
            sockets.append(raw_socket)
    raw_socket = getattr(socket_client, 'socket', None)
    if raw_socket is not None:
        sockets.append(raw_socket)

    for obj in reversed(sockets):
        closer = getattr(obj, 'close', None)
        if not callable(closer):
            continue
        try:
            closer()
        except Exception:
            continue
