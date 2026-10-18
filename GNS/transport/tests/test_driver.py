from django.test import TestCase

from transport.form_choices import available_drivers_queryset
from transport.forms import TruckForm
from transport.models import Driver, Truck, TruckType


class DriverAssignmentTests(TestCase):
    def setUp(self):
        self.truck_type = TruckType.objects.create(type='Цистерна')
        self.driver = Driver.objects.create(full_name='Иванов Иван Иванович')
        self.inactive_driver = Driver.objects.create(
            full_name='Петров Пётр Петрович',
            is_active=False,
        )
        self.truck = Truck.objects.create(
            registration_number='AI 0008-1',
            type=self.truck_type,
            car_brand='МАЗ',
        )

    def test_truck_form_saves_without_driver(self):
        form = TruckForm(data={
            'registration_number': 'AH 0193-1',
            'type': self.truck_type.pk,
            'car_brand': 'МАЗ',
            'is_active': True,
            'is_on_station': False,
            'driver': '',
        })
        self.assertTrue(form.is_valid(), form.errors)
        truck = form.save()
        self.assertIsNone(truck.driver)

    def test_truck_form_assigns_free_driver(self):
        form = TruckForm(
            data={
                'registration_number': self.truck.registration_number,
                'type': self.truck_type.pk,
                'car_brand': 'МАЗ',
                'is_active': True,
                'is_on_station': False,
                'driver': self.driver.pk,
            },
            instance=self.truck,
        )
        self.assertTrue(form.is_valid(), form.errors)
        truck = form.save()
        self.assertEqual(truck.driver, self.driver)

    def test_busy_driver_not_in_queryset_for_other_truck(self):
        self.truck.driver = self.driver
        self.truck.save(update_fields=['driver'])

        other_truck = Truck.objects.create(
            registration_number='AM 5448-1',
            type=self.truck_type,
            car_brand='МАЗ',
        )
        available_ids = set(
            available_drivers_queryset(other_truck).values_list('pk', flat=True)
        )
        self.assertNotIn(self.driver.pk, available_ids)

        form = TruckForm(
            data={
                'registration_number': other_truck.registration_number,
                'type': self.truck_type.pk,
                'car_brand': 'МАЗ',
                'is_active': True,
                'is_on_station': False,
                'driver': self.driver.pk,
            },
            instance=other_truck,
        )
        self.assertFalse(form.is_valid())
        self.assertIn('driver', form.errors)

    def test_current_driver_stays_in_queryset_even_if_inactive(self):
        self.truck.driver = self.inactive_driver
        self.truck.save(update_fields=['driver'])

        available_ids = set(
            available_drivers_queryset(self.truck).values_list('pk', flat=True)
        )
        self.assertIn(self.inactive_driver.pk, available_ids)

        other_truck = Truck.objects.create(
            registration_number='AM 5448-1',
            type=self.truck_type,
        )
        other_ids = set(
            available_drivers_queryset(other_truck).values_list('pk', flat=True)
        )
        self.assertNotIn(self.inactive_driver.pk, other_ids)

    def test_inactive_driver_hidden_from_create_form(self):
        form = TruckForm()
        choice_ids = {value for value, _ in form.fields['driver'].choices if value}
        self.assertIn(self.driver.pk, choice_ids)
        self.assertNotIn(self.inactive_driver.pk, choice_ids)
