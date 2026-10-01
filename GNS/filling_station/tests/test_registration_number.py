from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase

from filling_station.forms import TrailerForm, TruckForm
from filling_station.models import Trailer, TrailerType, Truck, TruckType
from filling_station.services.transport import (
    _format_registration_number,
    format_trailer_display,
    format_trailer_hmi,
    format_truck_display,
    format_truck_hmi,
    normalize_registration_number,
    to_storage,
    validate_trailer_input,
    validate_truck_input,
)


class RegistrationNumberFormatTests(SimpleTestCase):
    def test_cyrillic_plate_variants_for_miriada(self):
        expected = 'АС 5512-1'
        for variant in ('АС5512-1', 'АС55121', 'АС 5512-1'):
            with self.subTest(variant=variant):
                self.assertEqual(_format_registration_number(variant), expected)

    def test_latin_plate_normalized_for_miriada(self):
        self.assertEqual(_format_registration_number('AC55121'), 'AC 5512-1')
        self.assertEqual(_format_registration_number('AP71081'), 'AP 7108-1')
        self.assertEqual(_format_registration_number('AP 7108-1'), 'AP 7108-1')

    def test_to_storage_lower_compact(self):
        self.assertEqual(to_storage('AI 0008-1'), 'ai00081')
        self.assertEqual(to_storage('AI0008-1'), 'ai00081')
        self.assertEqual(to_storage('ai00081'), 'ai00081')
        self.assertEqual(to_storage('A 3779B-1'), 'a3779b1')
        self.assertEqual(normalize_registration_number('AC5512-1'), 'ac55121')

    def test_truck_display_and_hmi(self):
        self.assertEqual(format_truck_display('ai00081'), 'AI 0008-1')
        self.assertEqual(format_truck_hmi('ai00081'), 'AI0008-1')
        self.assertEqual(format_truck_display('AI 0008-1'), 'AI 0008-1')

    def test_trailer_display_and_hmi(self):
        self.assertEqual(format_trailer_display('a3779b1'), 'A 3779B-1')
        self.assertEqual(format_trailer_hmi('a3779b1'), 'A3779B-1')

    def test_validate_truck_input(self):
        self.assertEqual(validate_truck_input('AH 0193-1'), 'ah01931')
        with self.assertRaises(ValidationError):
            validate_truck_input('AH0193-1')
        with self.assertRaises(ValidationError):
            validate_truck_input('АН 0193-1')  # кириллица
        with self.assertRaises(ValidationError):
            validate_truck_input('ah01931')

    def test_validate_trailer_input(self):
        self.assertEqual(validate_trailer_input('A 3779B-1'), 'a3779b1')
        with self.assertRaises(ValidationError):
            validate_trailer_input('A3779B-1')
        with self.assertRaises(ValidationError):
            validate_trailer_input('А 3779B-1')


class RegistrationNumberFormTests(TestCase):
    def setUp(self):
        self.truck_type = TruckType.objects.create(type='Цистерна')
        self.trailer_type = TrailerType.objects.create(type='Полуприцеп цистерна')
        self.truck = Truck.objects.create(
            registration_number='ai00081',
            type=self.truck_type,
            car_brand='МАЗ',
        )

    def test_truck_form_accepts_display_and_stores_compact(self):
        form = TruckForm(data={
            'registration_number': 'AH 0193-1',
            'type': self.truck_type.pk,
            'car_brand': 'МАЗ',
            'is_active': True,
            'is_on_station': False,
        })
        self.assertTrue(form.is_valid(), form.errors)
        truck = form.save()
        self.assertEqual(truck.registration_number, 'ah01931')
        self.assertEqual(str(truck), 'AH 0193-1')

    def test_truck_form_rejects_compact_and_cyrillic(self):
        form = TruckForm(data={
            'registration_number': 'AH0193-1',
            'type': self.truck_type.pk,
            'is_active': True,
        })
        self.assertFalse(form.is_valid())
        self.assertIn('registration_number', form.errors)

    def test_truck_form_edit_shows_display(self):
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
        self.assertEqual(trailer.registration_number, 'a3779b1')
        self.assertEqual(str(trailer), 'A 3779B-1')

    def test_model_save_normalizes_hyphenated(self):
        truck = Truck(
            registration_number='AM 5448-1',
            type=self.truck_type,
        )
        truck.save()
        truck.refresh_from_db()
        self.assertEqual(truck.registration_number, 'am54481')
