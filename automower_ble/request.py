"""
    Script to generate request commands
"""

# Copyright: Alistair Francis <alistair@alistair23.me>

import unittest
import binascii

from .helpers import crc

import logging

logger = logging.getLogger(__name__)

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
        ("nextStartTime", ((4658, 1), (0x00, 0x00, 0x00))),
        ("override", ((4658, 2), (0x00, 0x00, 0x00))),
        ("request_trigger", ((4586, 4),(0x00, 0x00, 0x00))),
        ("keepalive", ((4674, 2), (0x00, 0x00, 0x00))),
        ("getStartupSequenceRequiredRequest", ((4698, 2), (0x00, 0x00, 0x00))),
        ("is_operator_loggedin", ((4664, 3), (0x00, 0x00, 0x00))),
        ("get_mode_request", ((4586, 1), (0x00, 0x00, 0x00))),
        ("get_serial_number", ((4698, 10), (0x00, 0x00, 0x00))),
        ("get_restriction_reason", ((4658, 0), (0x00, 0x00, 0x00))),
        ("get_number_of_tasks", ((4690, 4), (0x00, 0x00, 0x00))),
        ("set_mode_request", ((4586, 0), (0x00, 0x00, 0x00, 0x00)))
    ]
)


class MowerRequest:
    def __init__(self, channel_id: int):
        self.channel_id = channel_id

    def __generate_request_template(self, boolean_value_false:bool = False) -> bytearray:
        data = bytearray()

        # Hard coded value
        data.append(0x02)

        # Hard coded value
        data.append(0xFD)

        # Length, Updated later
        data.append(0x00)

        # Hard coded value
        data.append(0x00)

        # print(f'using channelid : {hex(self.channel_id)}')
        # ChannelID
        id = self.channel_id.to_bytes(4, byteorder="little")
        data.append(id[0])
        data.append(id[1])
        data.append(id[2])
        data.append(id[3])

        # The third argument to e(int i10, int i11, boolean z10, T t10). Almost always 1
        if not boolean_value_false:
            data.append(0x01)
        else:
            data.append(0x00)

        # CRC, Updated later
        data.append(0x00)

        # Hard coded value
        data.append(0x00)

        # Hard coded value
        data.append(0xAF)

        return data

    def __generate_standard_request(self, request, boolean_value_false:bool = False) -> bytearray:
        data = self.__generate_request_template(boolean_value_false)

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
        logger.debug(f'pin => {pin}')
        print(f'pin => {binascii.hexlify(pin)}')
        
        #0002003305
        #0533000200 -> int : 22330475008
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
    
    def generate_request_trigger_request(self) -> bytearray:
        data = self.__generate_standard_request("request_trigger")
        return self.__finalise_standard_request(data)
    
    def generate_keepalive_request(self) -> bytearray:
        data = self.__generate_standard_request("keepalive")
        return self.__finalise_standard_request(data)
    
    def generate_request_override(self) -> bytearray:
        data = self.__generate_standard_request("override")
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

    def generate_request_next_start_time(self) -> bytearray:
        data = self.__generate_standard_request("nextStartTime")
        return self.__finalise_standard_request(data)
    

#set_mode_request
    def generate_set_request_mode_of_operation(self, mode) -> bytearray:
        data = self.__generate_standard_request("set_mode_request")
        match mode:
            case "auto":
                data[16] = 0x00
            case "manual":
                data[16] = 0x01
            case "home":
                data[16] = 0x02
            case "demo":
                data[16] = 0x03
            case "poi":
                data[16] = 0x04
            case _:
                return None

        return self.__finalise_standard_request(data)

    def generate_request_mode_of_operation(self, mode) -> bytearray:
        data = self.__generate_standard_request("modeOfOperation")

        match mode:
            case "auto":
                data[16] = 0x00
            case "manual":
                data[16] = 0x01
            case "home":
                data[16] = 0x02
            case "demo":
                data[16] = 0x03
            case "poi":
                data[16] = 0x04
            case _:
                return None

        return self.__finalise_standard_request(data)
    
    def generate_set_override_mow(self, duration) -> bytearray:
        data = self.__generate_standard_request("overrideDuration")
        data[15] = 0x00
        data[16] = 0x04
        data[17] = 0x00
        
        d = duration.to_bytes(2, byteorder="little")
        data[18] = d[0]
        data[19] = d[1]
        
        data[20] = 0x00
        data[21] = 0x00
        return self.__finalise_standard_request(data)

    def generate_request_override_duration(self, duration) -> bytearray:
        data = self.__generate_standard_request("overrideDuration")

        match duration:
            case "30min" : 
                data[15] = 0x00
                data[16] = 0x04
                data[17] = 0x00
                data[18] = 0x08
                data[19] = 0x07
                data[20] = 0x00
                data[21] = 0x00
            case "3hours": #181193933824
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

    def generate_getStartupSequenceRequiredRequest(self) -> bytearray:
        data = self.__generate_standard_request('getStartupSequenceRequiredRequest')
        return self.__finalise_standard_request(data)
    
    def generate_is_operator_loggedin_request(self) -> bytearray:
        data = self.__generate_standard_request("is_operator_loggedin" )
        return self.__finalise_standard_request(data)
    
    def generate_get_mode_request(self) -> bytearray:
        data = self.__generate_standard_request("get_mode_request")
        return self.__finalise_standard_request(data)
    
    def generate_get_serial_number(self) -> bytearray:
        data = self.__generate_standard_request("get_serial_number")
        return self.__finalise_standard_request(data)
    
    def generate_get_restriction_reason(self) -> bytearray:
        data = self.__generate_standard_request("get_restriction_reason")
        return self.__finalise_standard_request(data)
    
    def generate_get_number_of_tasks(self) -> bytearray:
        data = self.__generate_standard_request("get_number_of_tasks")
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

    def test_pin_request(self):
        request = MowerRequest(0x13a51453)
        self.assertEqual(
            binascii.hexlify(request.generate_request_pin(1331)),
            b"02fd12005314a513011300af38120400020033050103"
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
        #request = MowerRequest(0x5798CA1A)
        request = MowerRequest(0x13A51453)

        self.assertEqual(
            binascii.hexlify(request.generate_set_request_mode_of_operation("manual")),
            b"02fd11005314a513015400afea1100000100003303"
            #b"02fd11001aca9857013400afea110100010000fe03",
        )

    def test_generate_request_override_duration(self):
        request = MowerRequest(0x5798CA1A)

        self.assertEqual(
            binascii.hexlify(request.generate_request_override_duration("3hours")),
            b"02fd14001aca985701fd00af321203000400302a00004603",
        )
        
    def test_generate_request_override_duration_30_min(self):
        request = MowerRequest(0x13a51453)
        self.assertEqual(
            binascii.hexlify(request.generate_request_override_duration("30min")),
            b"02fd14005314a513019d00af321203000400080700009603",
        )


    # def test_generate_request_park(self):
    #     request = MowerRequest(0x47603bb6)
        
    #     self.assertEqual(
    #         binascii.hexlify(request.generate_request_park()),
    #         b"02fd1000a84f571201f500af321205000000c703"
    #     )
if __name__ == "__main__":
    unittest.main()
