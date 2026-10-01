from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase

from filling_station.forms import TrailerForm, TruckForm
from filling_station.models import Trailer, TrailerType, Truck, TruckType
from filling_station.services.transport import (
    canonicalize_registration_number,
    find_transport_by_registration_number,
    format_trailer_hmi,
    format_truck_hmi,
    validate_trailer_input,
    validate_truck_input,
)


class RegistrationNumberFormatTests(SimpleTestCase):
    def test_canonicalize_truck(self):
        self.assertEqual(canonicalize_registration_number('ai00081'), 'AI 0008-1')
        self.assertEqual(canonicalize_registration_number('AI0008-1'), 'AI 0008-1')
        self.assertEqual(canonicalize_registration_number('AI 0008-1'), 'AI 0008-1')
        self.assertEqual(canonicalize_registration_number('Ai 0008-1'), 'AI 0008-1')

    def test_canonicalize_trailer(self):
        self.assertEqual(canonicalize_registration_number('a3779b1'), 'A 3779B-1')
        self.assertEqual(canonicalize_registration_number('A3779B-1'), 'A 3779B-1')
        self.assertEqual(canonicalize_registration_number('A 3779B-1'), 'A 3779B-1')

    def test_canonicalize_passthrough_service_labels(self):
        self.assertEqual(canonicalize_registration_number('Самовывоз'), 'Самовывоз')
        self.assertEqual(canonicalize_registration_number('camobxvoz'), 'camobxvoz')

    def test_truck_hmi(self):
        self.assertEqual(format_truck_hmi('ai00081'), 'AI0008-1')
        self.assertEqual(format_truck_hmi('AI 0008-1'), 'AI0008-1')

    def test_trailer_hmi(self):
        self.assertEqual(format_trailer_hmi('a3779b1'), 'A3779B-1')
        self.assertEqual(format_trailer_hmi('A 3779B-1'), 'A3779B-1')

    def test_validate_truck_input(self):
        self.assertEqual(validate_truck_input('AH 0193-1'), 'AH 0193-1')
        with self.assertRaises(ValidationError):
            validate_truck_input('AH0193-1')
        with self.assertRaises(ValidationError):
            validate_truck_input('АН 0193-1')  # кириллица
        with self.assertRaises(ValidationError):
            validate_truck_input('ah01931')

    def test_validate_trailer_input(self):
        self.assertEqual(validate_trailer_input('A 3779B-1'), 'A 3779B-1')
        with self.assertRaises(ValidationError):
            validate_trailer_input('A3779B-1')
        with self.assertRaises(ValidationError):
            validate_trailer_input('А 3779B-1')


class RegistrationNumberFormTests(TestCase):
    def setUp(self):
        self.truck_type = TruckType.objects.create(type='Цистерна')
        self.trailer_type = TrailerType.objects.create(type='Полуприцеп цистерна')
        self.truck = Truck.objects.create(
            registration_number='AI 0008-1',
            type=self.truck_type,
            car_brand='МАЗ',
        )

    def test_truck_form_accepts_display_and_stores_display(self):
        form = TruckForm(data={
            'registration_number': 'AH 0193-1',
            'type': self.truck_type.pk,
            'car_brand': 'МАЗ',
            'is_active': True,
            'is_on_station': False,
        })
        self.assertTrue(form.is_valid(), form.errors)
        truck = form.save()
        self.assertEqual(truck.registration_number, 'AH 0193-1')
        self.assertEqual(str(truck), 'AH 0193-1')

    def test_truck_form_rejects_compact_and_cyrillic(self):
        form = TruckForm(data={
            'registration_number': 'AH0193-1',
            'type': self.truck_type.pk,
            'is_active': True,
        })
        self.assertFalse(form.is_valid())
        self.assertIn('registration_number', form.errors)

    def test_truck_form_edit_keeps_field_as_is(self):
        form = TruckForm(instance=self.truck)
        self.assertEqual(form.initial['registration_number'], 'AI 0008-1')

    def test_trailer_form_accepts_display(self):
        form = TrailerForm(data={
            'truck': self.truck.pk,
            'registration_number': 'A 3779B-1',
            'type': self.trailer_type.pk,
            'is_active': True,
            'is_on_station': False,
        })
        self.assertTrue(form.is_valid(), form.errors)
        trailer = form.save()
        self.assertEqual(trailer.registration_number, 'A 3779B-1')
        self.assertEqual(str(trailer), 'A 3779B-1')

    def test_model_save_canonicalizes_compact(self):
        truck = Truck(
            registration_number='am54481',
            type=self.truck_type,
        )
        truck.save()
        truck.refresh_from_db()
        self.assertEqual(truck.registration_number, 'AM 5448-1')

    def test_find_by_intellect_compact(self):
        truck, trailer = find_transport_by_registration_number('ai00081')
        self.assertEqual(truck, self.truck)
        self.assertIsNone(trailer)

    def test_find_by_hmi(self):
        truck, trailer = find_transport_by_registration_number('AI0008-1')
        self.assertEqual(truck, self.truck)
        self.assertIsNone(trailer)
