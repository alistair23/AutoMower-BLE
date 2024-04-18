import unittest
from automower_ble.mower import Mower
from automower_ble.request import *

class TestStringMethods(unittest.TestCase):
    def test_generate_request_setup_channel_id(self):
        request_one = MowerRequest(1197489075)
        request_two = MowerRequest(1739453030)

        self.assertEqual(
            binascii.hexlify(request_one.generate_request_setup_channel_id()),
            b"02fd160000000000002e14b33b6047000000004d61696e001b03",
        )
        self.assertEqual(
            binascii.hexlify(request_one.generate_request_handshake()),
            b"02fd0a00b33b6047005d08012803",
        )

        self.assertEqual(
            binascii.hexlify(request_two.generate_request_setup_channel_id()),
            b"02fd160000000000002e1466f2ad67000000004d61696e003403",
        )
        self.assertEqual(
            binascii.hexlify(request_two.generate_request_handshake()),
            b"02fd0a0066f2ad6700f908012803",
        )

    def test_generate_request_device_type(self):
        request_two = MowerRequest(1739453030)

        self.assertEqual(
            binascii.hexlify(request_two.generate_request_device_type()),
            b"02fd100066f2ad6701d700af5a1209000000b703",
        )

    def test_generate_request_pin(self):
        request_two = MowerRequest(1739453030)

        self.assertEqual(
            binascii.hexlify(request_two.generate_request_pin(7201)),
            b"02fd120066f2ad6701ad00af381204000200211c7d03",
        )

    def test_generate_request_remaining_charge_time(self):
        request_one = MowerRequest(1197489075)

        self.assertEqual(
            binascii.hexlify(request_one.generate_request_remaining_charge_time()),
            b"02fd1000b33b6047017300af0a1016000000b803",
        )

    def test_generate_request_is_charging(self):
        request_one = MowerRequest(1197489075)

        self.assertEqual(
            binascii.hexlify(request_one.generate_request_is_charging()),
            b"02fd1000b33b6047017300af0a10150000003003",
        )

    def test_generate_request_battery_level(self):
        request_one = MowerRequest(1197489075)

        self.assertEqual(
            binascii.hexlify(request_one.generate_request_battery_level()),
            b"02fd1000b33b6047017300af0a1014000000bf03",
        )

    def test_generate_request_mode_of_operation(self):
        request = MowerRequest(0x5798CA1A)

        self.assertEqual(
            binascii.hexlify(request.generate_request_mode_of_operation("manual")),
            b"02fd11001aca9857013400afea1100000100003303",
        )

    def test_generate_request_override_duration(self):
        request = MowerRequest(0x5798CA1A)

        self.assertEqual(
            binascii.hexlify(request.generate_request_override_duration("3hours")),
            b"02fd14001aca985701fd00af321203000400302a00004603",
        )


if __name__ == "__main__":
    unittest.main()
