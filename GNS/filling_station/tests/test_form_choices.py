from django.test import TestCase

from filling_station.form_choices import format_trailer_choice, format_truck_choice
from filling_station.forms import TrailerForm
from filling_station.models import Trailer, TrailerType, Truck, TruckType


class TransportChoiceLabelTests(TestCase):
    def setUp(self):
        self.truck_type = TruckType.objects.create(type='Трал')
        self.trailer_type = TrailerType.objects.create(type='Полуприцеп')
        self.truck = Truck.objects.create(
            registration_number='AM5448-1',
            car_brand='МАЗ',
            type=self.truck_type,
        )
        self.trailer = Trailer.objects.create(
            registration_number='AE1234-5',
            trailer_brand='Schmitz',
            type=self.trailer_type,
            truck=self.truck,
        )

    def test_format_truck_choice_includes_brand_and_type(self):
        label = format_truck_choice(self.truck)
        self.assertIn('AM5448-1', label)
        self.assertIn('МАЗ', label)
        self.assertIn('Трал', label)

    def test_format_trailer_choice_includes_brand_and_type(self):
        label = format_trailer_choice(self.trailer)
        self.assertIn('AE1234-5', label)
        self.assertIn('Schmitz', label)
        self.assertIn('Полуприцеп', label)

    def test_trailer_form_truck_field_uses_extended_label(self):
        form = TrailerForm()
        labels = [label for _, label in form.fields['truck'].choices if _]
        self.assertTrue(any('МАЗ' in label and 'Трал' in label for label in labels))
