from django.test import SimpleTestCase

from opcua.melsoft_words import (
    MELSOFT_STRING_WORD_COUNT,
    coerce_vehicle_select_text,
    empty_melsoft_words,
    is_empty_melsoft_buffer,
    pack_melsoft_string,
    unpack_melsoft_string,
)


class MelsoftWordsTests(SimpleTestCase):
    def test_pack_golden_a_7583_1(self):
        words = pack_melsoft_string('A 7583-1')
        self.assertEqual(len(words), MELSOFT_STRING_WORD_COUNT)
        self.assertEqual(words[:4], [8257, 13623, 13112, 12589])
        self.assertTrue(all(w == 0 for w in words[4:]))

    def test_pack_empty_is_seventeen_zeros(self):
        self.assertEqual(pack_melsoft_string(''), empty_melsoft_words())
        self.assertEqual(pack_melsoft_string(None), empty_melsoft_words())

    def test_unpack_golden_and_truncates(self):
        words = [8257, 13623, 13112, 12589] + [0] * 13
        self.assertEqual(unpack_melsoft_string(words), 'A 7583-1')

    def test_unpack_stops_at_zero_byte(self):
        # "AB" + terminator in first two words partly
        words = [0x4241, 0] + [0] * 15  # 'A','B'
        self.assertEqual(unpack_melsoft_string(words), 'AB')

    def test_roundtrip(self):
        text = 'AI0008-1'
        self.assertEqual(unpack_melsoft_string(pack_melsoft_string(text)), text)

    def test_non_ascii_packs_zeros(self):
        words = pack_melsoft_string('АИ0008-1')
        self.assertEqual(words, empty_melsoft_words())

    def test_is_empty_buffer(self):
        self.assertTrue(is_empty_melsoft_buffer(None))
        self.assertTrue(is_empty_melsoft_buffer(''))
        self.assertTrue(is_empty_melsoft_buffer('   '))
        self.assertTrue(is_empty_melsoft_buffer([0] * 17))
        self.assertFalse(is_empty_melsoft_buffer([8257] + [0] * 16))
        self.assertFalse(is_empty_melsoft_buffer('1    AI0008-1'))

    def test_coerce_words_and_string(self):
        words = pack_melsoft_string('AH0193-1')
        self.assertEqual(coerce_vehicle_select_text(words), 'AH0193-1')
        self.assertEqual(coerce_vehicle_select_text('AH0193-1'), 'AH0193-1')
        self.assertEqual(coerce_vehicle_select_text([0] * 17), '')
