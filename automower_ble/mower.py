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

from .protocol import (
    BLEClient,
    Command,
    MowerState,
    MowerActivity,
    ModeOfOperation,
    TaskInformation,
)
from .models import MowerModels
from .error_codes import ErrorCodes

from bleak import BleakScanner

logger = logging.getLogger(__name__)


class Mower(BLEClient):
    def __init__(self, channel_id: int, address, pin=None):
        super().__init__(channel_id, address, pin)

    async def set_parameter(self, parameter_name: str, **kwargs) -> None:
        """
        This is the same function as get_parameter but with a different name to make syntax a bit more clear.
        It also does not handle any response even though it upstream reads the response."""
        await self.get_parameter(parameter_name, **kwargs)

    async def get_parameter(self, parameter_name: str, **kwargs):
        """
        This function is used to get a parameter from the mower. It will send a request to the mower and then
        wait for a response. The response will be parsed and returned to the caller.
        """
        command = Command(self.channel_id, self.protocol[parameter_name])
        request = command.generate_request(**kwargs)
        response = await self._request_response(request)
        
        if response is None:
            return None

        if command.validate_response(response) is False:
            logger.error("Response failed validation")
            return None

        response_dict = command.parse_response(response)
        if ( not response_dict is None and 
            len(response_dict) == 1
        ):  # If there is only one key in the response, return the value
            return response_dict["response"]
        else:
            return response_dict

    async def get_manufacturer(self) -> str | None:
        """Get the mower manufacturer"""
        model = await self.get_parameter("deviceType")
        if model is None:
            return None

        model_information = MowerModels.get(
            (model["deviceType"], model["deviceSubType"])
        )
        if model_information is None:
            return f"Unknown Manufacturer ({model['deviceType']}, {model['deviceSubType']})"

        return model_information.manufacturer

    async def get_model(self) -> str | None:
        """Get the mower model"""
        model = await self.get_parameter("deviceType")
        if model is None:
            return None

        model_information = MowerModels.get(
            (model["deviceType"], model["deviceSubType"])
        )
        if model_information is None:
            return f"Unknown Model ({model['deviceType']}, {model['deviceSubType']})"

        return model_information.model

    async def is_charging(self) -> bool:
        if await mower.get_parameter("isCharging"):
            return True
        else:
            return False

    async def battery_level(self) -> int | None:
        """Query the mower battery level"""
        return await self.get_parameter("batteryLevel")

    async def mower_state(self) -> MowerState | None:
        """Query the mower state"""
        state = await self.get_parameter("mowerState")
        if state is None:
            return None
        return MowerState(state)

    async def mower_next_start_time(self) -> datetime | None:
        """Query the mower next start time"""
        next_start_time = await self.get_parameter("nextStartTime")
        if next_start_time is None or next_start_time == 0:
            return None
        return datetime.fromtimestamp(next_start_time, timezone.utc)

    async def mower_activity(self) -> MowerActivity | None:
        """Query the mower activity"""
        activity = await self.get_parameter("mowerActivity")
        if activity is None:
            return None
        return MowerActivity(activity)

    async def mower_override(self, duration_hours: int = 3) -> None:
        """
        Force the mower to run for the specified duration in hours.
        """
        # Set mode of operation to manual:
        await self.set_parameter("setModeOfOperation", mode=ModeOfOperation.MANUAL)

        # Set the duration of operation:
        await self.set_parameter("overrideDuration", duration=duration_hours * 3600)
    
    async def set_mower_override_duration_in_seconds(self, duration_in_seconds: int) -> None:
        await self.set_parameter("overrideDuration", duration=duration_in_seconds)
        

    async def mower_pause(self):
        await self.set_parameter("pause")

    async def mower_resume(self):
        await self.set_parameter("resume")

    async def mower_park(self):
        await self.set_parameter("park")
    
    async def send_keepalive(self):
        await self.set_parameter("keepalive")
        return True
    
    async def send_operator_pin_request(self, pin):
        await self.set_parameter('pin', code=pin)
        return True
    
    async def get_startupsequence_required_request(self)-> bool:
        required = await self.get_parameter('getStartupSequenceRequiredRequest')
        return required
    
    async def is_operator_loggedin(self):
        result = await self.get_parameter('isOperatorLoggedIn')
        return result
    
    async def get_serial_number(self):
        sn = await self.get_parameter('serialNumber')
        return sn
    
    async def get_restriction_reason(self):
        rr = await self.get_parameter('getRestrictionReason')
        if rr is None:
            return None
        return RestrictionReason(rr)
    
    async def get_number_of_tasks(self):
        response = await self.get_parameter('getNumberOfTasks')
        return response
    
    async def get_mode_of_operation(self):
        mode_response = await self.get_parameter('getModeOfOperation')
        if mode_response is None:
            return None
        return ModeOfOperation(mode_response)
    
    async def set_mode_of_operation(self, mode:ModeOfOperation):
        await self.set_parameter('setModeOfOperation', mode=mode.value )
    
    async def start_trigger_request(self) -> None:
        request_trigger_response = await self.get_parameter('requestTrigger')
        if request_trigger_response is None:
            return None
        return True
        
    async def get_task(self, taskid: int) -> TaskInformation | None:
        """
        Get information about a specific task
        """
        task = await self.get_parameter("getTask", task=taskid)
        if task is None:
            return None
        return TaskInformation(datetime.fromtimestamp(task['next_start_time'], timezone.utc),
                               task['duration_in_seconds'],
                               task['on_monday'] == 1,
                               task['on_tuesday']== 1,
                               task['on_wednesday']== 1,
                               task['on_thursday']== 1,
                               task['on_friday']== 1,
                               task['on_saturday']== 1,
                               task['on_sunday']== 1,
                               )


async def main(mower: Mower):
    device = await BleakScanner.find_device_by_address(mower.address)

    if device is None:
        print("Unable to connect to device address: " + mower.address)
        print(
            "Please make sure the device address is correct, the device is powered on and nearby"
        )
        return

    await mower.connect(device)

    manufacturer = await mower.get_manufacturer()
    print("Mower manufacturer: " + manufacturer)

    model = await mower.get_model()
    print("Mower model: " + model)

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
    print(
        "\t"
        + datetime.fromtimestamp(last_message["messageTime"], timezone.utc).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    )
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
