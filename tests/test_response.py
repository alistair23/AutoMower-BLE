import unittest
import json
from importlib.resources import files
from automower_ble.protocol import *
from automower_ble.models import MowerModels

class TestRequestMethods(unittest.TestCase):
    def setUp(self):
        with files("automower_ble").joinpath("protocol.json").open("r") as f:
            self.protocol = json.load(f)  # Load the parameters to have them available

    def test_decode_response_device_type(self):
        command = Command(1197489078, parameter=self.protocol["deviceType"])

        response = command.parse_response(
            bytearray.fromhex("02fd1300b63b604701e601af5a1209000002001701c803")
        )
        self.assertEqual(
            MowerModels[(response["deviceType"], response["deviceSubType"])],
            "305",
        )

        response = command.parse_response(
            bytearray.fromhex("02fd130038e38f0b01dc01af5a1209000002000c005903")
        )
        self.assertEqual(
            MowerModels[(response["deviceType"], response["deviceSubType"])],
            "315",
        )
    def test_decode_response_is_charging(self):
        command = Command(1197489078, self.protocol["isCharging"])

        self.assertEqual(
            command.parse_response(
                bytearray.fromhex("02fd1200b63b604701db01af0a101500000100011603")
            )["response"],
            True,
        )
        self.assertEqual(
            command.parse_response(
                bytearray.fromhex("02fd1200b63b604701db01af0a101500000100004803")
            )['response'],
            False,
        )

    def test_decode_response_mower_state(self):
        command = Command(1197489078, self.protocol["mowerState"])

        self.assertNotIn(
            command.parse_response(bytearray.fromhex("02fd1200b33b6047010901afea110100000100008103"))['response'],
            [1,2,3,4,5,6,7,8,9,10,12,13,14], # 11=unknown
        )

        command = Command(876143061, self.protocol["mowerState"])
        self.assertEqual(
            command.parse_response(
                bytearray.fromhex("02fd1200d5e13834012301afea110200000100033a03")
            )['response'],
            3, # 3=error
        )

    def test_decode_response_mower_activity(self):
        response = Command(1197489078, self.protocol["mowerActivity"])

        self.assertEqual(
            response.parse_response(
                bytearray.fromhex("02fd1200b33b6047010901afea110200000100026403")
            )["response"],
            2,  # 2 = goingOut
        )

if __name__ == "__main__":
    unittest.main()
