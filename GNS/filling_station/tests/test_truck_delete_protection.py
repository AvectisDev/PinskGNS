from django.contrib.auth.models import User
from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse

from filling_station.models import BalloonsBatch, BatchStatus, Truck, TruckType


class TruckDeleteProtectionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='truck_delete_user', password='x')
        self.truck_type = TruckType.objects.create(type='Трал')
        self.truck = Truck.objects.create(
            registration_number='5555AA-7',
            type=self.truck_type,
            car_brand='МАЗ',
        )
        self.batch = BalloonsBatch.objects.create(
            batch_type='l',
            truck=self.truck,
            reader_number=6,
            ttn_id=1,
            amount_of_ttn=1,
            status=BatchStatus.PAUSED,
            balloons_type='e',
            user=self.user,
        )

    def test_delete_truck_with_batch_shows_error_and_keeps_truck(self):
        url = reverse('filling_station:truck_delete', args=[self.truck.pk])
        response = self.client.post(url, follow=False)

        self.assertEqual(response.status_code, 302)
        self.assertTrue(Truck.objects.filter(pk=self.truck.pk).exists())

        messages = [str(m) for m in get_messages(response.wsgi_request)]
        self.assertTrue(messages)
        self.assertTrue(
            any('Нельзя удалить' in message for message in messages),
            messages,
        )

    def test_delete_truck_without_relations_succeeds(self):
        free_truck = Truck.objects.create(
            registration_number='6666BB-7',
            type=self.truck_type,
            car_brand='МАЗ',
        )
        url = reverse('filling_station:truck_delete', args=[free_truck.pk])
        response = self.client.post(url)

        self.assertEqual(response.status_code, 302)
        self.assertFalse(Truck.objects.filter(pk=free_truck.pk).exists())
