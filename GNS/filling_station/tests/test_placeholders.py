from django.test import TestCase
from django.urls import reverse

from filling_station.models import Truck, TruckType


class SamovyvozListTests(TestCase):
    def setUp(self):
        self.truck_type = TruckType.objects.create(type='Трал')
        self.real_truck = Truck.objects.create(
            registration_number='AI 0008-1',
            car_brand='МАЗ',
            type=self.truck_type,
        )
        Truck.objects.create(
            registration_number='camobxvoz',
            car_brand='Самовывоз',
            type=self.truck_type,
        )

    def test_truck_list_hides_samovyvoz(self):
        response = self.client.get(reverse('filling_station:truck_list'))
        self.assertEqual(response.status_code, 200)
        brands = [t.car_brand for t in response.context['object_list']]
        self.assertIn('МАЗ', brands)
        self.assertNotIn('Самовывоз', brands)
