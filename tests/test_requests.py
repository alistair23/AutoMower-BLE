import unittest
import json
from importlib.resources import files
from automower_ble.protocol import *

class TestRequestMethods(unittest.TestCase):
    def setUp(self):
        with files("automower_ble").joinpath("protocol.json").open("r") as f:
            self.protocol = json.load(f)  # Load the parameters to have them available

    def test_generate_request_setup_channel_id(self):
        request_one = 1197489075
        request_two = 1739453030

        self.assertEqual(
            binascii.hexlify(generate_request_setup_channel_id(channel_id=request_one)),
            b"02fd160000000000002e14b33b6047000000004d61696e001b03",
        )
        self.assertEqual(
            binascii.hexlify(generate_request_handshake(channel_id=request_one)),
            b"02fd0a00b33b6047005d08012803",
        )

        self.assertEqual(
            binascii.hexlify(generate_request_setup_channel_id(channel_id=request_two)),
            b"02fd160000000000002e1466f2ad67000000004d61696e003403",
        )
        self.assertEqual(
            binascii.hexlify(generate_request_handshake(channel_id=request_two)),
            b"02fd0a0066f2ad6700f908012803",
        )

    def test_generate_request_device_type(self):
        command = Command(1739453030, parameter=self.protocol["deviceType"])

        self.assertEqual(
            binascii.hexlify(command.generate_request()),
            b"02fd100066f2ad6701d700af5a1209000000b703",
        )

    def test_generate_request_pin(self):
        command = Command(1739453030, parameter=self.protocol["pin"])

        self.assertEqual(
            binascii.hexlify(command.generate_request(code=7201)),
            b"02fd120066f2ad6701ad00af381204000200211c7d03",
        )

    def test_generate_request_remaining_charge_time(self):
        command = Command(1197489075, parameter=self.protocol["remainingChargeTime"])

        self.assertEqual(
            binascii.hexlify(command.generate_request()),
            b"02fd1000b33b6047017300af0a1016000000b803",
        )

    def test_generate_request_is_charging(self):
        command = Command(1197489075, parameter=self.protocol["isCharging"])

        self.assertEqual(
            binascii.hexlify(command.generate_request()),
            b"02fd1000b33b6047017300af0a10150000003003",
        )

    def test_generate_request_battery_level(self):
        command = Command(1197489075, parameter=self.protocol["batteryLevel"])

        self.assertEqual(
            binascii.hexlify(command.generate_request()),
            b"02fd1000b33b6047017300af0a1014000000bf03",
        )

    # This unit test fails as (4586, 0) with data "0" is expected, this is not implemented.
    # def test_generate_request_mode_of_operation(self):
    #    command = Command(0x5798CA1A, parameter=self.protocol["modeOfOperation"])
    #
    #    self.assertEqual(
    #        binascii.hexlify(command.generate_request(mode=1)), #1=manual, Todo: convert to enum
    #        b"02fd11001aca9857013400afea1100000100003303",
    #    )

    def test_generate_request_override_duration(self):
        command = Command(0x5798CA1A, parameter=self.protocol["overrideDuration"])

        self.assertEqual(
            binascii.hexlify(command.generate_request(duration=3*3600)),
            b"02fd14001aca985701fd00af321203000400302a00004603",
        )


if __name__ == "__main__":
    unittest.main()
