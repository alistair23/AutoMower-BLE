import unittest
import json
from importlib.resources import files
from automower_ble.protocol import Command, MowerState, MowerActivity
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
            MowerModels[(response["deviceType"], response["deviceSubType"])].model,
            "Automower 305",
        )

        response = command.parse_response(
            bytearray.fromhex("02fd130038e38f0b01dc01af5a1209000002000c005903")
        )
        self.assertEqual(
            MowerModels[(response["deviceType"], response["deviceSubType"])].model,
            "Automower 315",
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
            )["response"],
            False,
        )

    def test_decode_response_mower_state(self):
        command = Command(1197489078, self.protocol["mowerState"])

        self.assertNotIn(
            command.parse_response(
                bytearray.fromhex("02fd1200b33b6047010901afea110100000100008103")
            )["response"],
            [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 13, 14],  # 11=unknown
        )

        command = Command(876143061, self.protocol["mowerState"])
        self.assertEqual(
            command.parse_response(
                bytearray.fromhex("02fd1200d5e13834012301afea110200000100033a03")
            )["response"],
            MowerState.FATAL_ERROR.value,
        )

    def test_decode_response_mower_activity(self):
        response = Command(1197489078, self.protocol["mowerActivity"])

        self.assertEqual(
            response.parse_response(
                bytearray.fromhex("02fd1200b33b6047010901afea110200000100026403")
            )["response"],
            MowerActivity.GOING_OUT.value,  # 2 = goingOut
        )

    def test_decode_get_task_response(self):
        response = Command(1197489078, self.protocol["getTask"])
        decoded = response.parse_response(
            bytearray.fromhex(
                "02fd240025be246a010701af5212050000130000e1000038310000010001010001013003"
            )
        )

        self.assertEqual(
            decoded["next_start_time"],
            57600,
        )
        self.assertEqual(
            decoded["duration_in_seconds"],
            12600,  # 2 = goingOut
        )
        self.assertEqual(decoded["on_monday"], 1)
        self.assertEqual(decoded["on_tuesday"], 0)
        self.assertEqual(decoded["on_wednesday"], 1)
        self.assertEqual(decoded["on_thursday"], 1)
        self.assertEqual(decoded["on_friday"], 0)
        self.assertEqual(decoded["on_saturday"], 1)
        self.assertEqual(decoded["on_sunday"], 1)

    def test_decode_get_number_of_tasks_response(self):
        response = Command(0x13A51453, self.protocol["getNumberOfTasks"])
        self.assertEqual(
            response.parse_response(
                bytearray.fromhex("02fd150025be246a012e01af52120400000400010000004f03")
            )["response"],
            1,
        )


if __name__ == "__main__":
    unittest.main()
