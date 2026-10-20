"""Общие фабрики фикстур для тестов filling_station."""

from __future__ import annotations

from django.contrib.auth.models import User

from filling_station.models import Balloon, BalloonsBatch, BatchStatus, ReaderSettings
from transport.models import Trailer, TrailerType, Truck, TruckType

_truck_seq = 0
_trailer_seq = 0
_balloon_seq = 0
_reader_ips = 0


def make_user(*, pk: int = 1, username: str = 'batch_operator') -> User:
    """Возвращает пользователя с заданным pk (создаёт при отсутствии)."""
    try:
        return User.objects.get(pk=pk)
    except User.DoesNotExist:
        return User.objects.create_user(id=pk, username=username, password='x')


def make_truck_type(type_name: str = 'Трал') -> TruckType:
    """Создаёт тип грузовика."""
    return TruckType.objects.create(type=type_name)


def make_truck(
    *,
    registration_number: str | None = None,
    type_name: str = 'Трал',
    truck_type: TruckType | None = None,
    car_brand: str = 'МАЗ',
) -> Truck:
    """Создаёт грузовик с уникальным рег. номером."""
    global _truck_seq
    if truck_type is None:
        truck_type = make_truck_type(type_name)
    if registration_number is None:
        _truck_seq += 1
        # max_length=10, формат как на проде: «XX NNNN-N»
        registration_number = f'AA {_truck_seq:04d}-1'
    return Truck.objects.create(
        registration_number=registration_number,
        type=truck_type,
        car_brand=car_brand,
    )


def make_trailer(
    *,
    truck: Truck,
    registration_number: str | None = None,
) -> Trailer:
    """Создаёт прицеп для грузовика."""
    global _trailer_seq
    trailer_type = TrailerType.objects.create(type=f'Type{_trailer_seq}')
    _trailer_seq += 1
    if registration_number is None:
        registration_number = f'BB {_trailer_seq:04d}-1'
    return Trailer.objects.create(
        truck=truck,
        registration_number=registration_number,
        type=trailer_type,
        trailer_brand='МАЗ',
    )


def make_reader(
    number: int,
    *,
    function: str = 'l',
    status: str = 'empty',
    need_cache: bool = False,
) -> ReaderSettings:
    """Создаёт настройки RFID-считывателя."""
    global _reader_ips
    _reader_ips += 1
    return ReaderSettings.objects.create(
        number=number,
        ip=f'10.10.2.{_reader_ips}',
        status=status,
        function=function,
        need_cache=need_cache,
    )


def make_balloon(*, nfc_tag: str | None = None, user: User | None = None, **kwargs) -> Balloon:
    """Создаёт баллон с уникальной NFC-меткой (user=None, без дефолта pk=1)."""
    global _balloon_seq
    if nfc_tag is None:
        _balloon_seq += 1
        nfc_tag = f'test{_balloon_seq:06d}e0'
    # У модели default=1 на user — в тестах пользователя с pk=1 может не быть.
    kwargs.setdefault('user', user)
    return Balloon.objects.create(nfc_tag=nfc_tag, **kwargs)


def make_batch(
    *,
    batch_type: str = 'l',
    truck: Truck | None = None,
    trailer: Trailer | None = None,
    reader_number: int = 6,
    ttn_id: int = 14769,
    amount_of_ttn: int = 1,
    status: str = BatchStatus.ACTIVE,
    balloons_type: str = 'e',
    user: User | None = None,
    **kwargs,
) -> BalloonsBatch:
    """Создаёт партию приёмки/отгрузки."""
    if truck is None:
        truck = make_truck()
    if user is None:
        user = make_user()
    return BalloonsBatch.objects.create(
        batch_type=batch_type,
        truck=truck,
        trailer=trailer,
        reader_number=reader_number,
        ttn_id=ttn_id,
        amount_of_ttn=amount_of_ttn,
        status=status,
        balloons_type=balloons_type,
        user=user,
        **kwargs,
    )
