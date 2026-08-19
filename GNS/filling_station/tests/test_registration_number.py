from django.test import SimpleTestCase

from filling_station.services.transport import (
    _format_registration_number,
    normalize_registration_number,
)


class RegistrationNumberFormatTests(SimpleTestCase):
    def test_cyrillic_plate_variants_for_miriada(self):
        expected = 'АС 5512-1'
        for variant in ('АС5512-1', 'АС55121', 'АС 5512-1'):
            with self.subTest(variant=variant):
                self.assertEqual(_format_registration_number(variant), expected)

    def test_latin_plate_normalized(self):
        self.assertEqual(_format_registration_number('AC55121'), 'AC 5512-1')
        self.assertEqual(_format_registration_number('AP71081'), 'AP 7108-1')
        self.assertEqual(_format_registration_number('AP 7108-1'), 'AP 7108-1')

    def test_normalize_compact_form(self):
        self.assertEqual(normalize_registration_number('АС 5512-1'), 'АС55121')
        self.assertEqual(normalize_registration_number('AC5512-1'), 'AC55121')
