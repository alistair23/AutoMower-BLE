"""
    Script to generate request commands
"""

# Copyright: Alistair Francis <alistair@alistair23.me>

import unittest
import binascii

from .helpers import crc

Requests = dict(
    [
        ("pin", ((4664, 4), (0x00, 0x02, 0x00))),
        ("batteryLevel", ((4106, 20), (0x00, 0x00, 0x00))),
        ("deviceType", ((4698, 9), (0x00, 0x00, 0x00))),
        ("remainingChargeTime", ((4106, 22), (0x00, 0x00, 0x00))),
        ("isCharging", ((4106, 21), (0x00, 0x00, 0x00))),
        ("modeOfOperation", ((4586, 1), (0x00, 0x00, 0x00, 0x00))),
        ("mowerState", ((4586, 2), (0x00, 0x00, 0x00))),
        ("mowerActivity", ((4586, 3), (0x00, 0x00, 0x00))),
        ("resume", ((4586, 4), (0x00, 0x00, 0x00))),
        ("pause", ((4586, 5), (0x00, 0x00, 0x00))),
        ("errorCode", ((4586, 6), (0x00, 0x00, 0x00))),
        ("overrideDuration", ((4658, 3), (0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00))),
        ("park", ((4658, 5), (0x00, 0x00, 0x00))),
    ]
)


class MowerRequest:
    def __init__(self, channel_id: int):
        self.channel_id = channel_id

    def __generate_request_template(self) -> bytearray:
        data = bytearray()

        # Hard coded value
        data.append(0x02)

        # Hard coded value
        data.append(0xFD)

        # Length, Updated later
        data.append(0x00)

        # Hard coded value
        data.append(0x00)

        # ChannelID
        id = self.channel_id.to_bytes(4, byteorder="little")
        data.append(id[0])
        data.append(id[1])
        data.append(id[2])
        data.append(id[3])

        # The third argument to e(int i10, int i11, boolean z10, T t10). Almost always 1
        data.append(0x01)

        # CRC, Updated later
        data.append(0x00)

        # Hard coded value
        data.append(0x00)

        # Hard coded value
        data.append(0xAF)

        return data

    def __generate_standard_request(self, request) -> bytearray:
        data = self.__generate_request_template()

        request = Requests[request]
        command = request[0]
        major = command[0].to_bytes(2, byteorder="little")
        minor = command[1]
        payload = request[1]

        # 4664, 4
        data.append(major[0])
        data.append(major[1])
        data.append(minor)

        data = data + bytearray(payload)

        return data

    def __finalise_standard_request(self, data: bytearray) -> bytearray:
        # Length
        data[2] = len(data) - 2

        # CRC
        data[9] = crc(data, 1, 8)
        data.append(crc(data, 1, len(data) - 1))

        # Hard coded value
        data.append(0x03)

        return data

    def generate_request_setup_channel_id(self) -> bytearray:
        """
        Setup the channelID with an Automower, this is the first
        command that should be sent
        """
        data = bytearray()

        # Hard coded value
        data.append(0x02)

        # Hard coded value
        data.append(0xFD)

        # Length
        data.append(0x16)

        # Blank ChannelID
        data.append(0x00)
        data.append(0x00)
        data.append(0x00)
        data.append(0x00)
        data.append(0x00)
        data.append(0x00)

        data.append(0x2E)
        data.append(0x14)

        # New ChannelID
        id = self.channel_id.to_bytes(4, byteorder="little")
        data.append(id[0])
        data.append(id[1])
        data.append(id[2])
        data.append(id[3])

        # Hard coded values
        data.append(0x00)
        data.append(0x00)
        data.append(0x00)
        data.append(0x00)
        data.append(0x4D)
        data.append(0x61)
        data.append(0x69)
        data.append(0x6E)
        data.append(0x00)

        return self.__finalise_standard_request(data)

    def generate_request_handshake(self) -> bytearray:
        """
        Generate a request handshake. This should be called after
        `generate_request_setup_channel_id()` but before other
        commands
        """
        data = bytearray()

        # Hard coded value
        data.append(0x02)

        # Hard coded value
        data.append(0xFD)

        # Length
        data.append(0x0A)

        # Hard coded value
        data.append(0x00)

        # ChannelId
        id = self.channel_id.to_bytes(4, byteorder="little")
        data.append(id[0])
        data.append(id[1])
        data.append(id[2])
        data.append(id[3])

        # Hard coded value
        data.append(0x00)

        # CRC
        data.append(crc(data, 1, len(data) - 1))

        data.append(0x08)
        data.append(0x01)

        return self.__finalise_standard_request(data)

    def generate_request_pin(self, pin: int) -> bytearray:
        data = self.__generate_standard_request("pin")

        # Pin
        pin = pin.to_bytes(2, byteorder="little")
        data.append(pin[0])
        data.append(pin[1])

        return self.__finalise_standard_request(data)

    def generate_request_device_type(self) -> bytearray:
        data = self.__generate_standard_request("deviceType")
        return self.__finalise_standard_request(data)

    def generate_request_remaining_charge_time(self) -> bytearray:
        data = self.__generate_standard_request("remainingChargeTime")
        return self.__finalise_standard_request(data)

    def generate_request_is_charging(self) -> bytearray:
        data = self.__generate_standard_request("isCharging")
        return self.__finalise_standard_request(data)

    def generate_request_battery_level(self) -> bytearray:
        data = self.__generate_standard_request("batteryLevel")
        return self.__finalise_standard_request(data)

    def generate_request_pause(self) -> bytearray:
        data = self.__generate_standard_request("pause")
        return self.__finalise_standard_request(data)

    def generate_request_resume(self) -> bytearray:
        data = self.__generate_standard_request("resume")
        return self.__finalise_standard_request(data)

    def generate_request_park(self) -> bytearray:
        data = self.__generate_standard_request("park")
        return self.__finalise_standard_request(data)

    def generate_request_mower_state(self) -> bytearray:
        data = self.__generate_standard_request("mowerState")
        return self.__finalise_standard_request(data)

    def generate_request_mower_activity(self) -> bytearray:
        data = self.__generate_standard_request("mowerActivity")
        return self.__finalise_standard_request(data)

    def generate_request_error_code(self) -> bytearray:
        data = self.__generate_standard_request("errorCode")
        return self.__finalise_standard_request(data)

    def generate_request_mode_of_operation(self, mode) -> bytearray:
        data = self.__generate_standard_request("modeOfOperation")

        match mode:
            case "auto":
                data[16] = 0
            case "manual":
                data[16] = 1
            case "home":
                data[16] = 2
            case "demo":
                data[16] = 3
            case "poi":
                data[16] = 4
            case _:
                return None

        return self.__finalise_standard_request(data)

    def generate_request_override_duration(self, duration) -> bytearray:
        data = self.__generate_standard_request("overrideDuration")

        match duration:
            case "3hours":
                data[15] = 0x00
                data[16] = 0x04
                data[17] = 0x00
                data[18] = 0x30
                data[19] = 0x2A
                data[20] = 0x00
                data[21] = 0x00
            case "6hours":
                data[15] = 0x00
                data[16] = 0x04
                data[17] = 0x00
                data[18] = 0x60
                data[19] = 0x54
                data[20] = 0x00
                data[21] = 0x00
            case _:
                return None

        return self.__finalise_standard_request(data)


class TestStringMethods(unittest.TestCase):
    def test_generate_request_setup_channel_id(self):
        request_one = MowerRequest(1197489075)
        request_two = MowerRequest(1739453030)

        self.assertEqual(
            request_one.generate_request_setup_channel_id(),
            bytearray(
                [
                    0x02,
                    0xFD,
                    0x16,
                    0x00,
                    0x00,
                    0x00,
                    0x00,
                    0x00,
                    0x00,
                    0x2E,
                    0x14,
                    0xB3,
                    0x3B,
                    0x60,
                    0x47,
                    0x00,
                    0x00,
                    0x00,
                    0x00,
                    0x4D,
                    0x61,
                    0x69,
                    0x6E,
                    0x00,
                    0x1B,
                    0x03,
                ]
            ),
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
            request_two.generate_request_pin(7201),
            bytearray(
                [
                    0x02,
                    0xFD,
                    0x12,
                    0x00,
                    0x66,
                    0xF2,
                    0xAD,
                    0x67,
                    0x01,
                    0xAD,
                    0x00,
                    0xAF,
                    0x38,
                    0x12,
                    0x04,
                    0x00,
                    0x02,
                    0x00,
                    0x21,
                    0x1C,
                    0x7D,
                    0x03,
                ]
            ),
        )

    def test_generate_request_remaining_charge_time(self):
        request_one = MowerRequest(1197489075)

        self.assertEqual(
            request_one.generate_request_remaining_charge_time(),
            bytearray(
                [
                    0x02,
                    0xFD,
                    0x10,
                    0x00,
                    0xB3,
                    0x3B,
                    0x60,
                    0x47,
                    0x01,
                    0x73,
                    0x00,
                    0xAF,
                    0x0A,
                    0x10,
                    0x16,
                    0x00,
                    0x00,
                    0x00,
                    0xB8,
                    0x03,
                ]
            ),
        )

    def test_generate_request_is_charging(self):
        request_one = MowerRequest(1197489075)

        self.assertEqual(
            request_one.generate_request_is_charging(),
            bytearray(
                [
                    0x02,
                    0xFD,
                    0x10,
                    0x00,
                    0xB3,
                    0x3B,
                    0x60,
                    0x47,
                    0x01,
                    0x73,
                    0x00,
                    0xAF,
                    0x0A,
                    0x10,
                    0x15,
                    0x00,
                    0x00,
                    0x00,
                    0x30,
                    0x03,
                ]
            ),
        )

    def test_generate_request_battery_level(self):
        request_one = MowerRequest(1197489075)

        self.assertEqual(
            request_one.generate_request_battery_level(),
            bytearray(
                [
                    0x02,
                    0xFD,
                    0x10,
                    0x00,
                    0xB3,
                    0x3B,
                    0x60,
                    0x47,
                    0x01,
                    0x73,
                    0x00,
                    0xAF,
                    0x0A,
                    0x10,
                    0x14,
                    0x00,
                    0x00,
                    0x00,
                    0xBF,
                    0x03,
                ]
            ),
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
