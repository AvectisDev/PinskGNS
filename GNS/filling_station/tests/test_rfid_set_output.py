from django.test import SimpleTestCase

from filling_station.management.commands.rfid_utils.models import FeigProtocol
from filling_station.management.commands.rfid_utils.settings import COMMANDS, command_frame


class SetOutputCommandTests(SimpleTestCase):
    def test_read_complete_frame_has_duration_byte(self):
        frame = command_frame('read_complete')
        self.assertEqual(len(frame), 13)
        self.assertEqual(frame[4], 0x72)
        self.assertEqual(frame[5:11], bytes.fromhex('01 01 81 01 00 19'))
        rebuilt = FeigProtocol.create_request('SET_OUTPUT', bytes.fromhex('01 01 81 01 00 19'))
        self.assertEqual(rebuilt, frame)

    def test_read_complete_with_error_frame_has_duration_byte(self):
        frame = command_frame('read_complete_with_error')
        self.assertEqual(frame[5:11], bytes.fromhex('01 01 81 0B 00 14'))
        rebuilt = FeigProtocol.create_request('SET_OUTPUT', bytes.fromhex('01 01 81 0B 00 14'))
        self.assertEqual(rebuilt, frame)

    def test_old_five_byte_payload_does_not_match_settings(self):
        short = FeigProtocol.create_request('SET_OUTPUT', bytes.fromhex('01 01 81 01 00'))
        self.assertNotEqual(short, command_frame('read_complete'))
        self.assertEqual(short[1:3], bytes.fromhex('00 0C'))
        self.assertEqual(command_frame('read_complete')[1:3], bytes.fromhex('00 0D'))

    def test_commands_dict_contains_lamp_keys(self):
        self.assertIn('read_complete', COMMANDS)
        self.assertIn('read_complete_with_error', COMMANDS)
