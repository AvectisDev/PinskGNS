"""Async OPC UA клиент: подписка на теги и initial read."""

from __future__ import annotations

import logging
from typing import Any, Optional

from asyncua import Client, Node, ua
from asyncua.common.subscription import DataChangeEvent, StatusChangeEvent

from opcua.bridge.dispatcher import TriggerDispatcher
from opcua.registry import TAGS, node_id_to_name

logger = logging.getLogger('opcua')

SUBSCRIPTION_PERIOD_MS = 500


class OpcBridgeClient:
    """Держит сессию asyncua, подписки и снимок тегов."""

    def __init__(self, url: str, dispatcher: TriggerDispatcher) -> None:
        self.url = url
        self.dispatcher = dispatcher
        self.client = Client(url=url)
        self._nodes_by_name: dict[str, Node] = {}
        self._name_by_nodeid: dict[str, str] = node_id_to_name()
        self._subscription = None

    async def connect(self) -> None:
        self.client.connection_lost_callback = self._on_connection_lost
        await self.client.connect(auto_reconnect=True, reconnect_max_delay=5.0)
        logger.info('OPC UA подключено: %s', self.url)
        await self._resolve_nodes()

    async def _on_connection_lost(self, exc: BaseException) -> None:
        logger.error(
            'OPC UA связь потеряна (%s), пытаюсь переподключиться…',
            exc,
        )

    async def disconnect(self) -> None:
        try:
            if self._subscription is not None:
                await self._subscription.delete()
                self._subscription = None
        except Exception as error:
            logger.warning('Ошибка удаления subscription: %s', error)
        try:
            await self.client.disconnect()
        except Exception as error:
            logger.warning('Ошибка disconnect OPC: %s', error)
        finally:
            self.client.connection_lost_callback = None

    async def _resolve_nodes(self) -> None:
        self._nodes_by_name = {
            name: self.client.get_node(tag.node_id)
            for name, tag in TAGS.items()
        }

    async def initial_read(self) -> dict[str, Any]:
        """Читает все теги один раз после connect."""
        snapshot: dict[str, Any] = {}
        for name, node in self._nodes_by_name.items():
            try:
                value = await node.read_value()
                snapshot[name] = value
            except Exception as error:
                logger.error('Initial read %s failed: %s', name, error)
                snapshot[name] = None
        return snapshot

    async def write_tag(self, name: str, value: Any) -> None:
        node = self._nodes_by_name.get(name)
        if node is None:
            raise KeyError(f'Unknown tag: {name}')
        converted = await self._convert_for_write(node, value)
        await node.write_value(converted)
        self.dispatcher.update_tag(name, converted)
        logger.debug('OPC write %s=%s', name, value)

    async def _convert_for_write(self, node: Node, value: Any) -> Any:
        try:
            variant_type = await node.read_data_type_as_variant_type()
        except Exception:
            data_value = await node.read_data_value()
            variant_type = data_value.Value.VariantType

        if variant_type == ua.VariantType.Boolean:
            return bool(value)
        if variant_type in (
            ua.VariantType.SByte,
            ua.VariantType.Byte,
            ua.VariantType.Int16,
            ua.VariantType.UInt16,
            ua.VariantType.Int32,
            ua.VariantType.UInt32,
            ua.VariantType.Int64,
            ua.VariantType.UInt64,
        ):
            return int(value)
        if variant_type in (ua.VariantType.Float, ua.VariantType.Double):
            return float(value)
        if variant_type == ua.VariantType.String:
            return str(value)
        return value

    def resolve_tag_name(self, node: Node) -> Optional[str]:
        node_id_str = node.nodeid.to_string()
        name = self._name_by_nodeid.get(node_id_str)
        if name:
            return name
        # fallback: сравнить без лишних пробелов
        compact = node_id_str.replace(' ', '')
        for registered_id, registered_name in self._name_by_nodeid.items():
            if registered_id.replace(' ', '') == compact:
                return registered_name
        return None

    async def run_subscription_loop(self) -> None:
        """Подписка на все теги и обработка DataChangeEvent."""
        nodes = list(self._nodes_by_name.values())
        subscription = await self.client.create_subscription(SUBSCRIPTION_PERIOD_MS)
        self._subscription = subscription
        async with subscription:
            await subscription.subscribe_data_change(nodes)

            snapshot = await self.initial_read()
            logger.info('OPC initial snapshot: %s', snapshot)
            self.dispatcher.on_snapshot(snapshot, force_pending=True)

            async for event in subscription:
                if isinstance(event, DataChangeEvent):
                    await self._on_data_change(event)
                elif isinstance(event, StatusChangeEvent):
                    logger.warning('OPC subscription status: %s', event.notification)

    async def _on_data_change(self, event: DataChangeEvent) -> None:
        name = self.resolve_tag_name(event.node)
        if not name:
            logger.debug('OPC data change неизвестного node %s', event.node)
            return
        value = event.value
        logger.debug('OPC change %s=%s', name, value)
        self.dispatcher.on_snapshot({name: value})
