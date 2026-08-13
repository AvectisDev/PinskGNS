from __future__ import annotations

from datetime import date
from typing import Any, Mapping, Optional

from django.conf import settings
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.db.models import Count, Q, QuerySet, Sum
from django.utils import timezone

from filling_station.models import Trailer, Truck
from autogas.models import AutoGasBatch

STATISTIC_CACHE_KEY = 'auto_gas_batch_statistic'

GAS_TYPE_BY_OPC_CODE = {
    2: 'СПБТ',
    3: 'ПБА',
}

BATCH_TYPE_BY_OPC_CODE = {
    1: 'l',
    2: 'u',
}

BATCH_TYPE_LABELS = {
    'l': 'Приёмка',
    'u': 'Отгрузка',
}


class AutoGasBatchError(Exception):
    """Ошибка обработки партии автоколонки."""


class ActiveBatchExistsError(AutoGasBatchError):
    """Уже есть активная партия."""


class NoActiveBatchError(AutoGasBatchError):
    """Нет активной партии для завершения."""


def resolve_batch_type(batch_type_code: Any) -> Optional[str]:
    allowed = {code for code, _ in settings.BATCH_TYPE_CHOICES}
    batch_type = BATCH_TYPE_BY_OPC_CODE.get(batch_type_code)
    if batch_type not in allowed:
        return None
    return batch_type


def resolve_gas_type(gas_type_code: Any) -> Optional[str]:
    allowed = {code for code, _ in settings.GAS_TYPE_CHOICES}
    gas_type = GAS_TYPE_BY_OPC_CODE.get(gas_type_code)
    if gas_type not in allowed:
        return None
    return gas_type


def get_truck_capacity(truck: Truck, trailer: Optional[Trailer] = None) -> Any:
    if truck.type.type == 'Цистерна':
        return truck.max_gas_volume
    if truck.type.type == 'Седельный тягач' and trailer:
        return trailer.max_gas_volume
    return None


def create_active_batch(
    *,
    batch_type: str,
    gas_type: str,
    truck: Truck,
    trailer: Optional[Trailer] = None,
) -> AutoGasBatch:
    with transaction.atomic():
        already_active = (
            AutoGasBatch.objects
            .select_for_update()
            .filter(is_active=True)
            .exists()
        )
        if already_active:
            raise ActiveBatchExistsError('Уже есть активная партия')
        try:
            return AutoGasBatch.objects.create(
                batch_type=batch_type,
                gas_type=gas_type,
                truck=truck,
                trailer=trailer,
                is_active=True,
            )
        except IntegrityError as exc:
            raise ActiveBatchExistsError('Уже есть активная партия') from exc


def complete_active_batch(batch_data: Mapping[str, Any]) -> AutoGasBatch:
    with transaction.atomic():
        batch = (
            AutoGasBatch.objects
            .select_for_update()
            .filter(is_active=True)
            .order_by('-begin_at', '-pk')
            .first()
        )
        if batch is None:
            raise NoActiveBatchError('Нет активной партии для завершения')

        batch.gas_amount = batch_data.get('gas_amount')
        batch.scale_empty_weight = batch_data.get('truck_empty_weight')
        batch.scale_full_weight = batch_data.get('truck_full_weight')
        batch.weight_gas_amount = batch_data.get('weight_gas_amount')
        batch.is_active = False
        batch.completed_at = timezone.now()
        batch.save(update_fields=[
            'gas_amount',
            'scale_empty_weight',
            'scale_full_weight',
            'weight_gas_amount',
            'is_active',
            'completed_at',
        ])
        return batch


def get_today_active_batches() -> QuerySet[AutoGasBatch]:
    return AutoGasBatch.objects.filter(
        is_active=True,
        begin_at__date=timezone.localdate(),
    ).select_related('truck', 'trailer')


def with_completed_at_on_deactivate(data: Mapping[str, Any]) -> dict[str, Any]:
    payload = dict(data.items())
    if not payload.get('is_active', True):
        payload['completed_at'] = timezone.now()
    return payload


def clear_statistic_cache() -> None:
    cache.delete(STATISTIC_CACHE_KEY)


def get_batch_statistic(*, use_cache: bool = True) -> dict[str, Any]:
    if use_cache:
        cached = cache.get(STATISTIC_CACHE_KEY)
        if cached is not None:
            return cached
    data = build_batch_statistic()
    cache.set(STATISTIC_CACHE_KEY, data)
    return data


def build_batch_statistic(today: Optional[date] = None) -> dict[str, Any]:
    today = today or timezone.localdate()
    first_day = today.replace(day=1)
    response: dict[str, Any] = {
        'loading_batch': {},
        'unloading_batch': {},
    }

    period_specs = (
        (
            Q(begin_at__date__gte=first_day, batch_type='l'),
            'last_month_loading_batches',
            'last_month_loading_weight',
        ),
        (
            Q(begin_at__date__gte=first_day, batch_type='u'),
            'last_month_unloading_batches',
            'last_month_unloading_weight',
        ),
        (
            Q(begin_at__date=today, batch_type='l'),
            'today_loading_batches',
            'today_loading_weight',
        ),
        (
            Q(begin_at__date=today, batch_type='u'),
            'today_unloading_batches',
            'today_unloading_weight',
        ),
    )

    for filters, count_name, weight_name in period_specs:
        rows = (
            AutoGasBatch.objects
            .filter(filters)
            .values('gas_type', 'batch_type')
            .annotate(**{
                count_name: Count('id'),
                weight_name: Sum('weight_gas_amount'),
            })
        )
        for row in rows:
            section = 'loading_batch' if row['batch_type'] == 'l' else 'unloading_batch'
            gas_type = row['gas_type']
            bucket = response[section].setdefault(gas_type, {})
            bucket.update(row)

    active_batch = (
        AutoGasBatch.objects
        .select_related('truck', 'trailer')
        .filter(is_active=True)
        .first()
    )
    if active_batch:
        response['active_batch'] = {
            'batch_type': BATCH_TYPE_LABELS.get(active_batch.batch_type, 'Отгрузка'),
            'gas_type': active_batch.gas_type,
            'car_brand': active_batch.truck.car_brand,
            'truck_number': active_batch.truck.registration_number,
            'trailer_number': (
                active_batch.trailer.registration_number if active_batch.trailer else None
            ),
            'truck_gas_capacity': (
                active_batch.truck.max_gas_volume if active_batch.truck.max_gas_volume else 0
            ),
            'scale_empty_weight': (
                active_batch.scale_empty_weight if active_batch.scale_empty_weight else 0
            ),
            'scale_full_weight': (
                active_batch.scale_full_weight if active_batch.scale_full_weight else 0
            ),
        }

    return response
