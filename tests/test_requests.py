import unittest
import json
from importlib.resources import files
from automower_ble.protocol import BLEClient, Command, ModeOfOperation
import binascii


class TestRequestMethods(unittest.TestCase):
    def setUp(self):
        with files("automower_ble").joinpath("protocol.json").open("r") as f:
            self.protocol = json.load(f)  # Load the parameters to have them available

    def test_generate_request_setup_channel_id(self):
        client_one = BLEClient(1197489075, "00:00:00:00:00:00")
        client_two = BLEClient(1739453030, "00:00:00:00:00:00")

        self.assertEqual(
            binascii.hexlify(client_one.generate_request_setup_channel_id()),
            b"02fd160000000000002e14b33b6047000000004d61696e001b03",
        )
        self.assertEqual(
            binascii.hexlify(client_one.generate_request_handshake()),
            b"02fd0a00b33b6047005d08012803",
        )

        self.assertEqual(
            binascii.hexlify(client_two.generate_request_setup_channel_id()),
            b"02fd160000000000002e1466f2ad67000000004d61696e003403",
        )
        self.assertEqual(
            binascii.hexlify(client_two.generate_request_handshake()),
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

    def test_generate_request_set_mode_of_operation(self):
        command = Command(0x5798CA1A, parameter=self.protocol["setModeOfOperation"])

        self.assertEqual(
            binascii.hexlify(command.generate_request(mode=ModeOfOperation.AUTO.value)),
            b"02fd11001aca9857013400afea1100000100003303",
        )

    def test_generate_request_get_mode_of_operation(self):
        command = Command(0x5798CA1A, parameter=self.protocol["getModeOfOperation"])

        self.assertEqual(
            binascii.hexlify(command.generate_request()),
            b"02fd10001aca9857010900afea1101000000e203",
        )

    def test_generate_request_override_duration(self):
        command = Command(0x5798CA1A, parameter=self.protocol["overrideDuration"])

        self.assertEqual(
            binascii.hexlify(command.generate_request(duration=3 * 3600)),
            b"02fd14001aca985701fd00af321203000400302a00004603",
        )

    def test_generate_get_task_request(self):
        command = Command(0x13a51453, parameter=self.protocol['getTask'])
        
        self.assertEqual(
            binascii.hexlify(command.generate_request(task=0)),
            b"02fd14005314a513019d00af52120500040000000000d203",
        )
    
    def test_generate_get_number_of_tasks_request(self):
        command = Command(0x13a51453, parameter=self.protocol['getNumberOfTasks'])
        
        self.assertEqual(
            binascii.hexlify(command.generate_request()),
            b"02fd10005314a513016900af5212040000008b03",
        )
        
    def test_generate_get_restriction_reason(self):
        command = Command(0x13a51453, parameter=self.protocol['getRestrictionReason'])
        
        self.assertEqual(
            binascii.hexlify(command.generate_request()),
            b"02fd10005314a513016900af3212000000004603",
        )
    
    def test_generate_get_serial_number(self):
        command = Command(0x13a51453, parameter=self.protocol['serialNumber'])
        
        self.assertEqual(
            binascii.hexlify(command.generate_request()),
            b"02fd10005314a513016900af5a120a0000003f03",
        )
        
    def test_generate_is_operator_loggedin_request(self):
        command = Command(0x13a51453, parameter=self.protocol['isOperatorLoggedIn'])
        
        self.assertEqual(
            binascii.hexlify(command.generate_request()),
            b"02fd10005314a513016900af3812030000000103",
        )
    
    def test_generate_getStartupSequenceRequiredRequest(self):
        command = Command(0x13a51453, parameter=self.protocol['getStartupSequenceRequiredRequest'])
        
        self.assertEqual(
            binascii.hexlify(command.generate_request()),
            b"02fd10005314a513016900af5a12020000002303",
        )
        
    def test_generate_keepalive_request(self):
        command = Command(0x13a51453, parameter=self.protocol['keepalive'])
        
        self.assertEqual(
            binascii.hexlify(command.generate_request()),
            b"02fd10005314a513016900af421202000000d903",
        )
        
    def test_generate_request_trigger_request(self):
        command = Command(0x13a51453, parameter=self.protocol['requestTrigger'])
        
        self.assertEqual(
            binascii.hexlify(command.generate_request()),
            b"02fd10005314a513016900afea11040000006303",
        )
        
    def test_generate_request_override(self):    
        command = Command(0x13a51453, parameter=self.protocol['override'])
        
        self.assertEqual(
            binascii.hexlify(command.generate_request()),
            b"02fd10005314a513016900af3212020000004103",
        )
if __name__ == "__main__":
    unittest.main()
