from django.test import TestCase

from transport.api.serializers import TruckSerializer
from transport.models import Driver, Truck, TruckType


class TruckSerializerDriverTests(TestCase):
    def setUp(self):
        self.truck_type = TruckType.objects.create(type='Цистерна')
        self.driver = Driver.objects.create(
            last_name='Иванов',
            first_name='Иван',
            middle_name='Иванович',
            phone='+375(29)123-45-78',
        )
        self.truck = Truck.objects.create(
            registration_number='AI 0008-1',
            type=self.truck_type,
            car_brand='МАЗ',
            driver=self.driver,
        )

    def test_includes_nested_driver(self):
        data = TruckSerializer(self.truck).data
        self.assertEqual(data['driver'], {
            'id': self.driver.pk,
            'last_name': 'Иванов',
            'first_name': 'Иван',
            'middle_name': 'Иванович',
            'phone': '+375(29)123-45-78',
        })

    def test_driver_is_null_when_not_assigned(self):
        truck = Truck.objects.create(
            registration_number='AM 5448-1',
            type=self.truck_type,
        )
        data = TruckSerializer(truck).data
        self.assertIsNone(data['driver'])
