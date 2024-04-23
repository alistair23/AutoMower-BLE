"""
    The top level script to connect and communicate with the mower
    This sends requests and decodes responses. This is an example of
    how the request and response classes can be used.
"""

# Copyright: Alistair Francis <alistair@alistair23.me>

import argparse
import asyncio
import logging
from datetime import datetime, timezone

from .protocol import *
from .models import MowerModels
from .error_codes import ErrorCodes

from bleak import BleakScanner

logger = logging.getLogger(__name__)

MTU_SIZE = 20


class Mower(BLEClient):
    def __init__(self, channel_id: int, address):
        super().__init__(channel_id, address)

    async def set_parameter(self, parameter_name: str, **kwargs)->None:
        """
        This is the same function as get_parameter but with a differerent name to make syntax a bit more clear.
        It also does not handle any response even though it upstream reads the response."""
        self.get_parameter(parameter_name, **kwargs)

    async def get_parameter(self, parameter_name: str, **kwargs):
        """
        This function is used to get a parameter from the mower. It will send a request to the mower and then
        wait for a response. The response will be parsed and returned to the caller.
        """
        command = Command(self.channel_id, self.protocol[parameter_name])
        request = command.generate_request(**kwargs)
        response = await self._request_response(request)
        if response == None:
            return None

        response_dict = command.parse_response(response)
        if len(response_dict) == 1: # If there is only one key in the response, return the value
            return response_dict["response"]
        else:
            return response_dict

    async def get_model(self)->str|None:
        """Get the mower model"""
        # Todo: Change MowerModels to an enum?
        model = await self.get_parameter("deviceType")
        if model is None:
            return None
        else:
            return MowerModels[(model["deviceType"], model["deviceSubType"])]

    async def is_charging(self)->bool:
        if await mower.get_parameter("isCharging"):
            return True
        else:
            return False

    async def battery_level(self)->int|None:
        """Query the mower battery level"""
        return await self.get_parameter("batteryLevel")

    async def mower_state(self)->MowerState|None:
        """Query the mower state"""
        state = await self.get_parameter("mowerState")
        if state is None:
            return None
        return MowerState(state)

    async def mower_next_start_time(self)->datetime|None:
        """Query the mower next start time"""
        next_start_time = await self.get_parameter("nextStartTime")
        if next_start_time is None or next_start_time == 0:
            return None
        return datetime.fromtimestamp(next_start_time, timezone.utc)

    async def mower_activity(self)->MowerActivity|None:
        """Query the mower activity"""
        activity = await self.get_parameter("mowerActivity")
        if activity is None:
            return None
        return MowerActivity(activity)

    async def mower_override(self, duration_hours: int = 3)->None:
        """
        Force the mower to run for the specified duration in hours.
        """
        # Set mode of operation to manual:
        await self.set_parameter("modeOfOperation", mode=ModeOfOperation.MANUAL)

        # Set the duration of operation:
        await self.set_parameter("overrideDuration", duration=duration_hours*3600)

    async def mower_pause(self):
        await self.set_parameter("pause")

    async def mower_resume(self):
        await self.set_parameter("resume")

    async def mower_park(self):
        await self.set_parameter("park")

async def main(mower: Mower):
    device = await BleakScanner.find_device_by_address(mower.address)

    if device is None:
        print("Unable to connect to device address: " + mower.address)
        print("Please make sure the device address is correct, the device is powered on and nearby")
        return

    await mower.connect(device)

    model = await mower.get_model()
    print("Connected to: " + model)

    charging = await mower.is_charging()
    if charging:
        print("Mower is charging")
    else:
        print("Mower is not charging")

    battery_level = await mower.battery_level()
    print("Battery is: " + str(battery_level) + "%")

    state = await mower.mower_state()
    print("Mower state: " + str(state))

    activity = await mower.mower_activity()
    print("Mower activity: " + str(activity))

    next_start_time = await mower.mower_next_start_time()
    if next_start_time:
        print("Next start time: " + next_start_time.strftime("%Y-%m-%d %H:%M:%S"))
    else:
        print("No next start time")

    statuses = await mower.get_parameter("getStatuses")
    for status, value in statuses.items():
        print(status, value)

    serial_number = await mower.get_parameter("serialNumber")
    print("Serial number: " + str(serial_number))

    last_message = await mower.get_parameter("getMessage", messageId=0)
    print("Last message: ")
    print("\t" + datetime.fromtimestamp(last_message["messageTime"], timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))
    print("\t" + ErrorCodes(last_message["code"]).name)
    # print("Running for 3 hours")
    # await mower.mower_override()

    # print("Pause")
    # await mower.mower_pause()

    # print("Resume")
    # await mower.mower_resume()

    # state = await mower.mower_state()
    # print("Mower state: " + state)

    # activity = await mower.mower_activity()
    # print("Mower activity: " + activity)

    await mower.disconnect()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    device_group = parser.add_mutually_exclusive_group(required=True)

    device_group.add_argument(
        "--address",
        metavar="<address>",
        help="the Bluetooth address of the Automower device to connect to",
    )

    args = parser.parse_args()

    mower = Mower(1197489078, args.address)

    log_level = logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)-15s %(name)-8s %(levelname)s: %(message)s",
    )

    asyncio.run(main(mower))
