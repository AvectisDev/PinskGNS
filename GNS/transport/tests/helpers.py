from filling_station.models import Trailer, TrailerType, Truck, TruckType


class TransportFixturesMixin:
    def setUp(self):
        super().setUp()
        self.truck_type = TruckType.objects.create(type='Цистерна')
        self.trailer_type = TrailerType.objects.create(type='Полуприцеп цистерна')
        self.truck = Truck.objects.create(
            registration_number='AA1234-7',
            type=self.truck_type,
            car_brand='МАЗ',
            is_on_station=False,
        )
        self.trailer = Trailer.objects.create(
            truck=self.truck,
            registration_number='AB1234-7',
            type=self.trailer_type,
            is_on_station=False,
        )
