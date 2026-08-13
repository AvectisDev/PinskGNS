from django.contrib.auth.models import User

from filling_station.models import Trailer, TrailerType, Truck, TruckType
from autogas.models import AutoGasBatch


class AutoGasFixturesMixin:
    def setUp(self):
        super().setUp()
        try:
            self.user = User.objects.get(pk=1)
        except User.DoesNotExist:
            self.user = User.objects.create_user(
                id=1,
                username='autogas_operator',
                password='x',
            )
        self.truck_type = TruckType.objects.create(type='Цистерна')
        self.tractor_type = TruckType.objects.create(type='Седельный тягач')
        self.trailer_type = TrailerType.objects.create(type='Полуприцеп цистерна')
        self.truck = Truck.objects.create(
            registration_number='1111AA-1',
            type=self.truck_type,
            car_brand='МАЗ',
            max_gas_volume=20000,
        )
        self.tractor = Truck.objects.create(
            registration_number='2222BB-2',
            type=self.tractor_type,
            car_brand='МАЗ',
            max_gas_volume=0,
        )
        self.trailer = Trailer.objects.create(
            truck=self.truck,
            registration_number='3333CC-3',
            type=self.trailer_type,
            max_gas_volume=18000,
        )

    def make_batch(self, **kwargs) -> AutoGasBatch:
        defaults = {
            'batch_type': 'l',
            'gas_type': 'СПБТ',
            'truck': self.truck,
            'is_active': False,
            'user': self.user,
        }
        defaults.update(kwargs)
        return AutoGasBatch.objects.create(**defaults)

