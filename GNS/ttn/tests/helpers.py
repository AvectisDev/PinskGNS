from django.contrib.auth.models import User

from filling_station.models import Truck, TruckType
from autogas.models import AutoGasBatch
from railway_service.models import RailwayTank
from ttn.models import City, Contractor


class TtnFixturesMixin:
    def setUp(self):
        super().setUp()
        try:
            self.user = User.objects.get(pk=1)
        except User.DoesNotExist:
            self.user = User.objects.create_user(
                id=1,
                username='ttn_operator',
                password='x',
            )
        self.truck_type = TruckType.objects.create(type='Цистерна')
        self.truck = Truck.objects.create(
            registration_number='1111AA-1',
            type=self.truck_type,
            car_brand='МАЗ',
        )
        self.tank = RailwayTank.objects.create(registration_number=55555)
        self.contractor = Contractor.objects.create(name='ОАО Тест')
        self.city = City.objects.create(name='Пинск')

    def make_auto_batch(self, **kwargs) -> AutoGasBatch:
        defaults = {
            'batch_type': 'l',
            'gas_type': 'СПБТ',
            'truck': self.truck,
            'is_active': False,
            'user': self.user,
        }
        defaults.update(kwargs)
        return AutoGasBatch.objects.create(**defaults)
