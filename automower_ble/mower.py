"""
    The top level script to connect and communicate with the mower
    This sends requests and decodes responses. This is an example of
    how the request and response classes can be used.
"""

# Copyright: Alistair Francis <alistair@alistair23.me>

import argparse
import asyncio
import logging, coloredlogs
from datetime import datetime, timezone

import binascii

from request import *
from response import MowerResponse

from bleak import BleakClient, BleakScanner
from bleak.backends.characteristic import BleakGATTCharacteristic

logger = logging.getLogger(__name__)
coloredlogs.install(level='DEBUG', logger=logger)

MTU_SIZE = 20


class Mower:
    def __init__(self, channel_id: int, address, pin=None):
        self.channel_id = channel_id
        self.address = address
        self.pin = pin

        self.request = MowerRequest(channel_id)
        self.response = MowerResponse(channel_id)

        self.queue = asyncio.Queue()

    async def _get_response(self):
        try:
            data = await asyncio.wait_for(self.queue.get(), timeout=10)

        except TimeoutError:
            logger.error("Unable to get response from device: '%s'", self.address)
            if self.is_connected():
                await self.disconnect()
            return None

        return data

    async def _write_data(self, data):
        logger.debug("Writing: " + str(binascii.hexlify(data)))

        chunk_size = MTU_SIZE - 3
        for chunk in (
            data[i : i + chunk_size] for i in range(0, len(data), chunk_size)
        ):
            await self.client.write_gatt_char(self.write_char, chunk, response=False)

        logger.debug("Finished writing")

    async def _read_data(self):
        data = await self._get_response()

        if data == None:
            return None

        if len(data) < 3:
            # We got such a small amount of data, let's try again
            data = data + await self._get_response()

            if len(data) < 3:
                # Something is wrong
                return None

        length = data[2] + 4

        logger.debug("Waiting for %d bytes", length)

        while len(data) != length:
            try:
                data = data + await asyncio.wait_for(self.queue.get(), timeout=5)
            except TimeoutError:
                logger.error(
                    "Unable to get full response from device: '%s', currently have"
                    + str(binascii.hexlify(data)),
                    self.address,
                )
                return None

        logger.warn("Final response: " + str(binascii.hexlify(data)))

        return data

    async def _request_response(self, request_data):
        i = 5
        while i > 0:
            try:
                # If there are previous responses, flush them out
                while not self.queue.empty():
                    await self.queue.get()

                await self._write_data(request_data)

                response_data = await self._read_data()
                if response_data == None:
                    i = i - 1
                    continue

            except asyncio.exceptions.CancelledError:
                logger.debug("Received CancelledError")
                i = i - 1
                continue

            break

        if i == 0:
            logger.error("Unable to communicate with device: '%s'", self.address)
            if self.is_connected():
                await self.disconnect()
            return None

        return response_data

    async def connect(self, device) -> bool:
        """
        Connect to a device and setup the channel

        Returns True on success
        """
        logger.info("[connect] starting scan...")

        if device is None:
            logger.error("[connect] could not find device with address '%s'", self.address)
            return False

        logger.info("[connect] connecting to device...")
        self.client = BleakClient(
            device, services=["98bd0001-0b0e-421a-84e5-ddbf75dc6de4"], use_cached=True,
            timeout=15.0
        )
        await self.client.connect()
        logger.info("[connect] connected")

        logger.info("[connect] pairing device...")
        await self.client.pair()
        logger.info("[connect] paired")

        self.client._backend._mtu_size = MTU_SIZE

        logger.info(f'Retrieving services from device')
        for service in self.client.services:
            logger.info("[Service] %s", service)

            for char in service.characteristics:
                if "read" in char.properties:
                    try:
                        value = await self.client.read_gatt_char(char.uuid)
                        logger.debug(
                            "  [Characteristic] %s (%s), Value: %r",
                            char,
                            ",".join(char.properties),
                            value,
                        )
                    except Exception as e:
                        logger.error(
                            "  [Characteristic] %s (%s), Error: %s",
                            char,
                            ",".join(char.properties),
                            e,
                        )

                else:
                    logger.debug(
                        "  [Characteristic] %s (%s)", char, ",".join(char.properties)
                    )
                if char.uuid == "98bd0002-0b0e-421a-84e5-ddbf75dc6de4":
                    self.write_char = char

                if char.uuid == "98bd0003-0b0e-421a-84e5-ddbf75dc6de4":
                    self.read_char = char

        async def notification_handler(
            characteristic: BleakGATTCharacteristic, data: bytearray
        ):
            logger.critical("[notification_handler] Received: " + str(binascii.hexlify(data)))
            await self.queue.put(data)

        await self.client.start_notify(self.read_char, notification_handler)

        await asyncio.sleep(5.0)

        logger.info(f'[connect] start requesting setup channel id')
        request = self.request.generate_request_setup_channel_id()
        response = await self._request_response(request)
        #logger.info(f'[connect] Got response from setup channel id : {response}')
        if response == None:
            return False

        ### TODO: Check response

        logger.info(f'[connect] start request handshake')
        request = self.request.generate_request_handshake()
        response = await self._request_response(request)
        #logger.info(f'[connect] got response {response}')
        if response == None:
            return False

        ### TODO: Check response


        if self.pin is not None:
            logger.info(f'[connect] pin is not None ([{self.pin}]). So start generating pin request')
            request = self.request.generate_request_pin(self.pin)
            response = await self._request_response(request)
            if response == None:
                return False

            ### TODO: Check response
        logger.info(f'[Mower:connect] Finished connecting return true')
        return True

    def is_connected(self) -> bool:
        return self.client.is_connected

    async def probe_gatts(self, device):
        if device is None:
            logger.error("could not find device with address '%s'", self.address)
            return False

        logger.info("connecting to device...")
        client = BleakClient(
            device, services=["98bd0001-0b0e-421a-84e5-ddbf75dc6de4"], use_cached=True
        )

        await client.connect()
        logger.info("connected")

        manufacture = None
        model = None
        device_type = None

        for service in client.services:
            logger.debug("[Service] %s", service)

            if service.uuid == "98bd0001-0b0e-421a-84e5-ddbf75dc6de4":
                manufacture = service.description

            for char in service.characteristics:
                if "read" in char.properties:
                    try:
                        value = await client.read_gatt_char(char.uuid)
                        logger.debug(
                            "  [Characteristic] %s (%s), Value: %r",
                            char,
                            ",".join(char.properties),
                            value,
                        )
                    except Exception as e:
                        logger.error(
                            "  [Characteristic] %s (%s), Error: %s",
                            char,
                            ",".join(char.properties),
                            e,
                        )

                else:
                    logger.debug(
                        "  [Characteristic] %s (%s)", char, ",".join(char.properties)
                    )

                if char.uuid == "00002a00-0000-1000-8000-00805f9b34fb":
                    model = await client.read_gatt_char(char)

                if char.uuid == "98bd0004-0b0e-421a-84e5-ddbf75dc6de4":
                    device_type = await client.read_gatt_char(char)

        await client.disconnect()

        return (manufacture, device_type.decode(), model.decode())

    async def get_model(self):
        """
        Get the mower model
        """
        request = self.request.generate_request_device_type()
        response = await self._request_response(request)
        if response == None:
            return False

        return self.response.decode_response_device_type(response)

    async def is_charging(self):
        request = self.request.generate_request_is_charging()
        response = await self._request_response(request)
        if response == None:
            return False

        return self.response.decode_response_is_charging(response)

    async def battery_level(self):
        """
        Query the mower battery level
        """
        request = self.request.generate_request_battery_level()
        response = await self._request_response(request)
        if response == None:
            return False

        return self.response.decode_response_battery_level(response)

    async def mower_state(self):
        request = self.request.generate_request_mower_state()
        response = await self._request_response(request)
        if response == None:
            return False

        return self.response.decode_response_mower_state(response)

    async def mower_next_start_time(self):
        request = self.request.generate_request_next_start_time()
        response = await self._request_response(request)
        if response == None:
            return False
        return self.response.decode_response_start_time(response)

    async def mower_activity(self):
        request = self.request.generate_request_mower_activity()
        response = await self._request_response(request)
        if response == None:
            return False

        return self.response.decode_response_mower_activity(response)
    
    async def set_mode_of_operation(self, mode: str):
        request = self.request.generate_set_request_mode_of_operation(mode)
        response = await self._request_response(request)
        return True
    
    
        
        

    async def mower_override(self):
        """
        Force the mower to run 3 hours
        """
        request = self.request.generate_request_mode_of_operation("manual")
        response = await self._request_response(request)
        if response == None:
            return False

        ### TODO: Check response

        request = self.request.generate_request_override_duration("3hours")
        response = await self._request_response(request)
        if response == None:
            return False

        ### TODO: Check response

    async def mower_pause(self):
        request = self.request.generate_request_pause()
        response = await self._request_response(request)
        if response == None:
            return False

        ### TODO: Check response

    async def mower_resume(self):
        request = self.request.generate_request_resume()
        response = await self._request_response(request)
        if response == None:
            return False

        ### TODO: Check response

    async def mower_park(self):
        request = self.request.generate_request_park()
        response = await self._request_response(request)
        print(f'Response on park request : {response}')
        if response == None:
            return False
        

        x = self.response.decode_response_park(response)
        print(f'x == {x}')
        if x == 1:
            return True
        return False
        ### TODO: Check response
    async def start_trigger_request(self):
        request = self.request.generate_request_trigger_request()
        response = await self._request_response(request)
        if response == None:
            return False
        return True
    
    async def send_keepalive(self) -> bool:
        request = self.request.generate_keepalive_request()
        response = await self._request_response(request)
        return self.response.decode_keepalive_response(response)
        
    async def generate_request_override(self):
        request = self.request.generate_request_override()
        response = await self._request_response(request)
        print(f'Response on generate_request_override {response}')
        if response == None:
            return False
        return True
    
    async def getStartupSequenceRequiredRequest(self)-> bool:
        request = self.request.generate_getStartupSequenceRequiredRequest()
        response = await self._request_response(request)
        return self.response.decode_getStartupSequenceRequiredResponse(response)
    
    async def is_operator_loggedin(self) -> bool:
        request = self.request.generate_is_operator_loggedin_request()
        response = await self._request_response(request)
        return self.response.decode_is_operator_loggedin_response(response)
    
    async def get_mode(self): 
        request = self.request.generate_get_mode_request()
        response = await self._request_response(request)
        return self.response.decode_get_mode_response(response)
    
    async def get_serial_number(self):
        request = self.request.generate_get_serial_number()
        response = await self._request_response(request)
        return self.response.decode_get_serial_number_response(response)
    
    async def get_restriction_reason(self):
        request = self.request.generate_get_restriction_reason()
        response = await self._request_response(request)
        return self.response.decode_get_restriction_reason_response(response)
    
    async def get_number_of_tasks(self):
        request = self.request.generate_get_number_of_tasks()
        response = await self._request_response(request)
        return self.response.decode_get_number_of_tasks_response(response)
    
    async def set_override_mow(self, duration: int):
        request = self.request.generate_request_override_duration("30min")
        response = await self._request_response(request)
        return self.response.decode_set_override_mow_response(response)
    
    
    async def send_operator_pin_request(self, pin):
        request = self.request.generate_request_pin(pin)
        response = await self._request_response(request)
        
        

    async def disconnect(self):
        """
        Disconnect from the mower, this should be called after every
        `connect()` before the Python script exits
        """

        await self.client.stop_notify(self.read_char)
        await self.queue.put(None)

        logger.info("disconnecting...")
        await self.client.disconnect()
        logger.info("disconnected")


async def main(mower):
    device = await BleakScanner.find_device_by_address(mower.address)

    if device is None:
        print("Unable to connect to device address: " + mower.address)
        print("Please make sure the device address is correct, the device is powered on and nearby")
        return

    await mower.connect(device)

    try: 
        model = await mower.get_model()
    except KeyError:
        model = "Untested"

    print("Connected to: " + model)

    charging = await mower.is_charging()
    if charging:
        print("Mower is charging")
    else:
        print("Mower is not charging")

    battery_level = await mower.battery_level()
    print("Battery is: " + str(battery_level) + "%")

    state = await mower.mower_state()
    print("Mower state: " + state)

    activity = await mower.mower_activity()
    print("Mower activity: " + activity)

    next_start_time = await mower.mower_next_start_time()
    if next_start_time:
        dt_start_time = datetime.fromtimestamp(next_start_time, tz=timezone.utc) # The mower does not have a timezone and therefore utc must be used for parsing
        print("Next start time: " + dt_start_time.strftime("%Y-%m-%d %H:%M:%S"))
    else:
        print("No next start time")

    print("Running for 3 hours")
    await mower.mower_override()
    print ("starting trigger request")
    await mower.start_trigger_request()
    print('Finished trigger request')
    await mower.generate_request_override()
    print('Finished override request')
    # print("Pause")
    # await mower.mower_pause()

    # print("Resume")
    # await mower.mower_resume()

    # print('Parking mower')
    # park_result = await mower.mower_park()
    # print(f'Finished parking mower request => {park_result}')
    
    # print('Start trigger request')
    # await mower.start_trigger_request()
    # print('---------------')

    print('Start get mower state request')
    state = await mower.mower_state()
    print("Mower state: " + state)

    print('Start get mower activity request')
    activity = await mower.mower_activity()
    print("Mower activity: " + activity)

    await mower.disconnect()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    device_group = parser.add_mutually_exclusive_group(required=True)

    device_group.add_argument(
        "--address",
        metavar="<address>",
        help="the Bluetooth address of the Automower device to connect to",
    )

    parser.add_argument(
        "--pin",
        metavar="<code>",
        type=int,
        default=None,
        help="Send PIN to authenticate. This feature is experimental and might not work.",
    )
    args = parser.parse_args()

    mower = Mower(1197489078, args.address, args.pin)

    log_level = logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)-15s %(name)-8s %(levelname)s: %(message)s",
    )

    asyncio.run(main(mower))
