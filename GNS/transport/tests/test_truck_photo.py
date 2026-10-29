from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from transport.forms import TruckForm
from transport.models import Truck, TruckType


def _tiny_jpeg() -> SimpleUploadedFile:
    # Minimal valid JPEG (1x1 pixel)
    content = (
        b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00'
        b'\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t'
        b'\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a'
        b'\x1f\x1e\x1d\x1a\x1c\x1c $.\' ",#\x1c\x1c(7),01444\x1f\'9=82<.342'
        b'\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00'
        b'\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00'
        b'\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b'
        b'\xff\xc4\x00\xb5\x10\x00\x02\x01\x03\x03\x02\x04\x03\x05\x05\x04\x04'
        b'\x00\x00\x01}\x01\x02\x03\x00\x04\x11\x05\x12!1A\x06\x13Qa\x07"q'
        b'\x142\x81\x91\xa1\x08#B\xb1\xc1\x15R\xd1\xf0$3br\x82'
        b'\t\n\x16\x17\x18\x19\x1a%&\',()*456789:CDEFGHIJSTUVWXYZcdefghij'
        b'stuvwxyz\x83\x84\x85\x86\x87\x88\x89\x8a\x92\x93\x94\x95\x96\x97'
        b'\x98\x99\x9a\xa2\xa3\xa4\xa5\xa6\xa7\xa8\xa9\xaa\xb2\xb3\xb4\xb5'
        b'\xb6\xb7\xb8\xb9\xba\xc2\xc3\xc4\xc5\xc6\xc7\xc8\xc9\xca\xd2\xd3'
        b'\xd4\xd5\xd6\xd7\xd8\xd9\xda\xe1\xe2\xe3\xe4\xe5\xe6\xe7\xe8\xe9'
        b'\xea\xf1\xf2\xf3\xf4\xf5\xf6\xf7\xf8\xf9\xfa'
        b'\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xaa\xff\xd9'
    )
    return SimpleUploadedFile('truck.jpg', content, content_type='image/jpeg')


class TruckPhotoFormTests(TestCase):
    def setUp(self):
        self.truck_type = TruckType.objects.create(type='Цистерна')

    def test_form_saves_without_photo(self):
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
        self.assertFalse(bool(truck.photo))

    def test_form_saves_uploaded_photo(self):
        form = TruckForm(
            data={
                'registration_number': 'AH 0193-1',
                'type': self.truck_type.pk,
                'car_brand': 'МАЗ',
                'is_active': True,
                'is_on_station': False,
                'driver': '',
            },
            files={'photo': _tiny_jpeg()},
        )
        self.assertTrue(form.is_valid(), form.errors)
        truck = form.save()
        self.assertTrue(truck.photo)
        self.assertTrue(truck.photo.name.startswith('trucks/'))
