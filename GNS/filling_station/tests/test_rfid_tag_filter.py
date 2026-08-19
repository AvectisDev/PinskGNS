from types import SimpleNamespace

from django.test import SimpleTestCase

from filling_station.management.commands.rfid_utils.models import (
    FeigReaderDevice,
    is_balloon_nfc_tag,
)


def _reader_settings(**overrides):
    defaults = {
        'number': 6,
        'ip': '10.10.2.26',
        'port': 10001,
        'status': 'empty',
        'function': 'l',
        'need_cache': False,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


class BalloonUidFilterTests(SimpleTestCase):
    def test_accepts_hex_uid_with_e0_suffix(self):
        self.assertTrue(is_balloon_nfc_tag('aabbccdde0'))
        self.assertTrue(is_balloon_nfc_tag('AABBCCDDE0'))

    def test_rejects_uid_without_e0_suffix(self):
        self.assertFalse(is_balloon_nfc_tag('aabbccdd'))
        self.assertFalse(is_balloon_nfc_tag('aabbccdde1'))

    def test_rejects_invalid_hex_and_empty(self):
        self.assertFalse(is_balloon_nfc_tag(''))
        self.assertFalse(is_balloon_nfc_tag(None))
        self.assertFalse(is_balloon_nfc_tag('nothexe0'))
        self.assertFalse(is_balloon_nfc_tag('abce0'))


class DuplicateTagFilterTests(SimpleTestCase):
    def test_first_tag_is_new_repeat_is_duplicate(self):
        device = FeigReaderDevice(_reader_settings())
        self.assertTrue(device.filter_duplicate_tag('aabbccdde0'))
        self.assertFalse(device.filter_duplicate_tag('aabbccdde0'))

    def test_duplicate_window_keeps_last_five_tags(self):
        device = FeigReaderDevice(_reader_settings())
        tags = [f'aabbccdd{i}e0' for i in range(5)]
        for tag in tags:
            self.assertTrue(device.filter_duplicate_tag(tag))
        self.assertFalse(device.filter_duplicate_tag(tags[0]))
        self.assertTrue(device.filter_duplicate_tag('ffffffffffffe0'))
        self.assertTrue(device.filter_duplicate_tag(tags[0]))
