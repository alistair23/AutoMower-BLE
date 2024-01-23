"""
    Script to decode response packets
"""

# Copyright: Alistair Francis <alistair@alistair23.me>

import unittest
import binascii

from .models import MowerModels
from .helpers import crc


class MowerResponse:
    def __init__(self, channel_id: int):
        self.channel_id = channel_id

    def decode_response_template(self, data: bytearray):
        if data[0] != 0x02:
            return None

        if data[1] != 0xFD:
            return None

        if data[3] != 0x00:
            return None

        id = self.channel_id.to_bytes(4, byteorder='little')
        if data[4] != id[0]:
            return None
        if data[5] != id[1]:
            return None
        if data[6] != id[2]:
            return None
        if data[7] != id[3]:
            return None

        if data[8] != 0x01:
            # This is a valid config, but we don't support it
            # return m1656b(decodeState, c10786f);
            return None

        if data[9] != crc(data, 1, 8):
            return None

        if data[10] != 0x01:
            return None

        if data[11] != 0xAF:
            return None

        # data[12], data[13] and data[14] are the request type

        if data[15] != 0x00:
            return None

        if data[16] != 0x00:
            return None

        return data

    def decode_response_device_type(self, data: bytearray):
        self.decode_response_template(data)

        # Length
        if data[17] != 0x02:
            return None

        if data[18] != 0x00:
            return None

        if data[21] != crc(data, 1, len(data) - 3):
            return None

        if data[22] != 0x03:
            return None

        return MowerModels[(data[19], data[20])]

    def decode_response_battery_level(self, data: bytearray):
        self.decode_response_template(data)

        # Length
        if data[17] != 0x01:
            return None

        if data[18] != 0x00:
            return None

        if data[20] != crc(data, 1, len(data) - 3):
            return None

        if data[21] != 0x03:
            return None

        return data[19]

    def decode_response_is_charging(self, data: bytearray):
        self.decode_response_template(data)

        # Length
        if data[17] != 0x01:
            return None

        if data[18] != 0x00:
            return None

        if data[20] != crc(data, 1, len(data) - 3):
            return None

        if data[21] != 0x03:
            return None

        return data[19]

    def decode_response_mower_state(self, data: bytearray):
        self.decode_response_template(data)

        # Length
        if data[17] != 0x01:
            return None

        if data[18] != 0x00:
            return None

        if data[20] != crc(data, 1, len(data) - 3):
            return None

        if data[21] != 0x03:
            return None

        state = data[19]

        match state:
            case 1:
                return "paused"
            case 2:
                return "stopped"
            case 3:
                return "error"
            case 4:
                return "fatalError"
            case 5:
                return "off"
            case 6:
                return "checkSafety"
            case 7:
                return "pendingStart"
            case 8:
                return "waitForSafetyPin"
            case 9:
                return "restricted"
            case 10:
                return "inOperation"
            case 11:
                return "unknown"
            case 12:
                return "connecting"
            case 13:
                return "pending"
            case 14:
                return "disconnected"
            case _:
                return "unknown"

    def decode_response_mower_activity(self, data: bytearray):
        self.decode_response_template(data)

        # Length
        if data[17] != 0x01:
            return None

        if data[18] != 0x00:
            return None

        if data[20] != crc(data, 1, len(data) - 3):
            return None

        if data[21] != 0x03:
            return None

        state = data[19]

        match state:
            case 2:
                return ""
            case 3:
                return "charging"
            case 4:
                return "goingOut"
            case 5:
                return "mowing"
            case 6:
                return "goingHome"
            case 7:
                return "parked"
            case 8:
                return "stoppedInGarden"
            case _:
                return "unknown"

class TestStringMethods(unittest.TestCase):
    def test_decode_response_device_type(self):
        response = MowerResponse(1197489078)

        self.assertEqual(response.decode_response_device_type(bytearray.fromhex("02fd1300b63b604701e601af5a1209000002001701c803")),
                         "305")

    def test_decode_response_is_charging(self):
        response = MowerResponse(1197489078)

        self.assertEqual(response.decode_response_is_charging(bytearray.fromhex("02fd1200b63b604701db01af0a101500000100011603")),
                         True)
        self.assertEqual(response.decode_response_is_charging(bytearray.fromhex("02fd1200b63b604701db01af0a101500000100004803")),
                         False)

    def test_decode_response_mower_state(self):
        response = MowerResponse(1197489078)

        self.assertEqual(response.decode_response_mower_state(bytearray.fromhex("02fd1200b33b6047010901afea110100000100008103")),
                         "unknown")

    def test_decode_response_mower_activity(self):
        response = MowerResponse(1197489078)

        self.assertEqual(response.decode_response_mower_activity(bytearray.fromhex("02fd1200b33b6047010901afea110200000100026403")),
                         "")


if __name__ == '__main__':
    unittest.main()
