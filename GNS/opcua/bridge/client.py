"""Async OPC UA клиент: подписка на теги и initial read."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

from asyncua import Client, Node, ua
from asyncua.common.subscription import DataChangeEvent, StatusChangeEvent

from opcua.bridge.dispatcher import TriggerDispatcher
from opcua.melsoft_words import (
    MELSOFT_STRING_WORD_COUNT,
    looks_like_melsoft_word_array,
)
from opcua.registry import TAGS, node_id_to_name

logger = logging.getLogger('opcua')

SUBSCRIPTION_PERIOD_MS = 500
INITIAL_READ_RETRY_SECONDS = 2.0
# Melsoft / GX Works2 STRING[n] часто экспонируется как ByteString или Byte[n].
PLC_STRING_FIXED_LEN = 32
# Порядок fallback: живой тип часто String, но Melsoft отклоняет String-запись.
STRING_WRITE_ENCODINGS = ('string', 'bytestring', 'byte_array')


class OpcBridgeClient:
    """Держит сессию asyncua, подписки и снимок тегов."""

    def __init__(self, url: str, dispatcher: TriggerDispatcher) -> None:
        self.url = url
        self.dispatcher = dispatcher
        self.client = Client(url=url)
        self._nodes_by_name: dict[str, Node] = {}
        self._name_by_nodeid: dict[str, str] = node_id_to_name()
        self._subscription = None
        # Успешный encoding Melsoft STRING[n] для тега (string|bytestring|byte_array).
        self._string_encoding_by_tag: dict[str, str] = {}

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

    async def initial_read_until_ready(self) -> dict[str, Any]:
        """Повторяет initial read, пока все узлы не читаются (без None)."""
        attempt = 0
        while True:
            attempt += 1
            snapshot = await self.initial_read()
            missing = [name for name, value in snapshot.items() if value is None]
            if not missing:
                return snapshot
            logger.warning(
                'Initial read неполный (попытка %s): нет %s тег(ов), повтор через %ss',
                attempt,
                len(missing),
                INITIAL_READ_RETRY_SECONDS,
            )
            await asyncio.sleep(INITIAL_READ_RETRY_SECONDS)

    @staticmethod
    def _is_bad_type_mismatch(error: BaseException) -> bool:
        return 'BadTypeMismatch' in str(error)

    @staticmethod
    def _fixed_string_bytes(value: Any, length: int = PLC_STRING_FIXED_LEN) -> bytes:
        """Кодирует значение в фиксированную STRING[n] (байты + нули)."""
        if value is None:
            raw = b''
        elif isinstance(value, (bytes, bytearray)):
            raw = bytes(value)
        else:
            raw = str(value).encode('utf-8')
        if len(raw) > length:
            raw = raw[:length]
        return raw.ljust(length, b'\x00')

    def _string_variant(self, encoding: str, value: Any) -> ua.Variant:
        """Строит Variant для Melsoft STRING[n] в одном из кодирований."""
        if encoding == 'string':
            return ua.Variant(
                '' if value is None else str(value),
                ua.VariantType.String,
            )
        if encoding == 'bytestring':
            return ua.Variant(
                self._fixed_string_bytes(value),
                ua.VariantType.ByteString,
            )
        if encoding == 'byte_array':
            padded = self._fixed_string_bytes(value)
            return ua.Variant(list(padded), ua.VariantType.Byte, is_array=True)
        raise ValueError(f'Unknown string encoding: {encoding}')

    async def _commit_write(
        self,
        node: Node,
        name: str,
        value: Any,
        variant: ua.Variant,
    ) -> None:
        # Melsoft MX OPC UA отклоняет запись со SourceTimestamp (BadWriteNotSupported).
        await node.write_value(ua.DataValue(variant))
        written = variant.Value
        self.dispatcher.update_tag(name, written)
        logger.debug(
            'OPC write %s=%s (VariantType=%s)',
            name,
            value,
            variant.VariantType,
        )

    @staticmethod
    def _uint16_word_array_variant(value: Any) -> ua.Variant:
        """ARRAY [0..16] OF WORD → UInt16[17] (pad/trunc до 17)."""
        words = [int(item) & 0xFFFF for item in value]
        if len(words) < MELSOFT_STRING_WORD_COUNT:
            words.extend([0] * (MELSOFT_STRING_WORD_COUNT - len(words)))
        elif len(words) > MELSOFT_STRING_WORD_COUNT:
            words = words[:MELSOFT_STRING_WORD_COUNT]
        return ua.Variant(words, ua.VariantType.UInt16, is_array=True)

    async def write_tag(self, name: str, value: Any) -> None:
        node = self._nodes_by_name.get(name)
        if node is None:
            raise KeyError(f'Unknown tag: {name}')

        # vehicle_select WORD[17]: не String/Byte[] fallback.
        if looks_like_melsoft_word_array(value):
            variant = self._uint16_word_array_variant(value)
            try:
                await self._commit_write(node, name, value, variant)
            except Exception as error:
                logger.error(
                    'OPC write %s=%r failed (VariantType=%s): %s',
                    name,
                    value,
                    variant.VariantType,
                    error,
                )
                raise
            return

        cached = self._string_encoding_by_tag.get(name)
        if cached is not None:
            variant = self._string_variant(cached, value)
            try:
                await self._commit_write(node, name, value, variant)
            except Exception as error:
                logger.error(
                    'OPC write %s=%r failed (VariantType=%s, encoding=%s): %s',
                    name,
                    value,
                    variant.VariantType,
                    cached,
                    error,
                )
                raise
            return

        variant = await self._to_variant(node, value)
        if variant.VariantType != ua.VariantType.String:
            try:
                await self._commit_write(node, name, value, variant)
            except Exception as error:
                logger.error(
                    'OPC write %s=%r failed (VariantType=%s): %s',
                    name,
                    value,
                    variant.VariantType,
                    error,
                )
                raise
            return

        # Melsoft STRING[n]: сервер часто отдаёт live String, но принимает
        # только ByteString / Byte[32]. Пробуем encodings по порядку.
        last_error: BaseException | None = None
        for encoding in STRING_WRITE_ENCODINGS:
            variant = self._string_variant(encoding, value)
            try:
                await self._commit_write(node, name, value, variant)
            except Exception as error:
                last_error = error
                if not self._is_bad_type_mismatch(error):
                    logger.error(
                        'OPC write %s=%r failed (VariantType=%s): %s',
                        name,
                        value,
                        variant.VariantType,
                        error,
                    )
                    raise
                logger.warning(
                    'OPC write %s=%r BadTypeMismatch as %s, пробуем следующий encoding',
                    name,
                    value,
                    encoding,
                )
                continue

            self._string_encoding_by_tag[name] = encoding
            if name.startswith('autogas.vehicle_select.') or encoding != 'string':
                logger.info(
                    'OPC string encoding для %s: %s (VariantType=%s)',
                    name,
                    encoding,
                    variant.VariantType,
                )
            return

        assert last_error is not None
        logger.error(
            'OPC write %s=%r failed после всех string encodings: %s',
            name,
            value,
            last_error,
        )
        raise last_error

    async def _resolve_variant_type(self, node: Node) -> tuple[ua.VariantType, Any]:
        """
        Тип для записи: предпочитаем VariantType живого значения,
        иначе data type node.
        """
        live_type: Optional[ua.VariantType] = None
        live_value: Any = None
        try:
            data_value = await node.read_data_value()
            if data_value.Value is not None:
                live_type = data_value.Value.VariantType
                live_value = data_value.Value.Value
        except Exception:
            pass

        declared_type: Optional[ua.VariantType] = None
        try:
            declared_type = await node.read_data_type_as_variant_type()
        except Exception:
            pass

        variant_type = live_type if live_type is not None else declared_type
        if variant_type is None:
            raise RuntimeError(f'Не удалось определить VariantType для {node}')
        return variant_type, live_value

    async def _to_variant(self, node: Node, value: Any) -> ua.Variant:
        variant_type, live_value = await self._resolve_variant_type(node)

        if variant_type == ua.VariantType.Boolean:
            return ua.Variant(bool(value), variant_type)
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
            # WORD[17] уже упакован вызывающим кодом.
            if looks_like_melsoft_word_array(value):
                return self._uint16_word_array_variant(value)
            # Legacy STRING[n] как Byte[]: живое значение — список байт (не UInt16).
            if (
                variant_type == ua.VariantType.Byte
                and isinstance(live_value, (list, tuple))
                and (not live_value or isinstance(live_value[0], int))
                and not looks_like_melsoft_word_array(live_value)
            ):
                padded = self._fixed_string_bytes(value)
                return ua.Variant(list(padded), ua.VariantType.Byte, is_array=True)
            return ua.Variant(int(value), variant_type)
        if variant_type in (ua.VariantType.Float, ua.VariantType.Double):
            return ua.Variant(float(value), variant_type)
        if variant_type == ua.VariantType.String:
            # Пустая строка — '', не Null.
            return ua.Variant('' if value is None else str(value), variant_type)
        if variant_type == ua.VariantType.ByteString:
            return ua.Variant(self._fixed_string_bytes(value), variant_type)
        return ua.Variant(value, variant_type)

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

            snapshot = await self.initial_read_until_ready()
            logger.info('OPC initial snapshot: %s', snapshot)
            self.dispatcher.on_snapshot(snapshot, force_pending=True)

            async for event in subscription:
                if isinstance(event, DataChangeEvent):
                    await self._on_data_change(event)
                elif isinstance(event, StatusChangeEvent):
                    logger.info('OPC subscription status: %s', event.notification)

    async def _on_data_change(self, event: DataChangeEvent) -> None:
        name = self.resolve_tag_name(event.node)
        if not name:
            logger.debug('OPC data change неизвестного node %s', event.node)
            return
        value = event.value
        previous = self.dispatcher.snapshot.get(name, object())
        if previous == value:
            return
        logger.debug('OPC change %s=%s', name, value)
        self.dispatcher.on_snapshot({name: value})
