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

from automower_ble.protocol import (
    BLEClient,
    Command,
    MowerState,
    MowerActivity,
    ModeOfOperation,
    ResponseResult,
    TaskInformation,
)
from automower_ble.models import MowerModels
from automower_ble.error_codes import ErrorCodes

from bleak import BleakScanner

logger = logging.getLogger(__name__)


class Mower(BLEClient):
    def __init__(self, channel_id: int, address, pin=None):
        super().__init__(channel_id, address, pin)
        self.keep_alive_event = asyncio.Event()

    async def connect(self, device) -> ResponseResult:
        """
        Connect to a device and setup the channel

        Returns a ResponseResult
        """
        status = await super().connect(device)
        if status == ResponseResult.OK:
            self.task = asyncio.create_task(self._keep_alive())
        return status

    async def disconnect(self):
        """
        Disconnect from the mower, this should be called after every
        `connect()` before the Python script exits
        """
        self.keep_alive_event.set()
        return await super().disconnect()

    async def _keep_alive(self):
        """
        Keep the connection alive by sending a request every 15 seconds.
        This is needed to prevent the connection from being closed by the mower.
        """
        while not self.keep_alive_event.is_set():
            try:
                if self.is_connected():
                    logger.debug("Sending keep alive")
                    await self.command("KeepAlive")
            except Exception as e:
                logger.warning(f"Failed to send keep alive: {e}")
            await asyncio.sleep(15)

    async def command(self, command_name: str, **kwargs):
        """
        This function is used to simplify the communication of the mower using the commands found in protocol.json.
        It will send a request to the mower and then wait for a response. The response will be parsed and returned to the caller.
        """
        command = Command(self.channel_id, (await self.get_protocol())[command_name])
        request = command.generate_request(**kwargs)
        response = await self._request_response(request)
        if response is None:
            return None

        if command.validate_command_response(response) is False:
            # Just log if the response is invalid as this has been seen with user
            # logs from official apps. I.e. it is somewhat expected.
            logger.warning("Response failed validation")

        response_dict = command.parse_response(response)
        if (
            response_dict is not None and len(response_dict) == 1
        ):  # If there is only one key in the response, return the value
            return response_dict["response"]
        else:
            return response_dict

    async def get_manufacturer(self) -> str | None:
        """Get the mower manufacturer"""
        model = await self.command("GetModel")
        if model is None:
            return None

        model_information = MowerModels.get(
            (model["deviceType"], model["deviceVariant"])
        )
        if model_information is None:
            return f"Unknown Manufacturer ({model['deviceType']}, {model['deviceVariant']})"

        return model_information.manufacturer

    async def get_model(self) -> str | None:
        """Get the mower model"""
        model = await self.command("GetModel")
        if model is None:
            return None

        model_information = MowerModels.get(
            (model["deviceType"], model["deviceVariant"])
        )
        if model_information is None:
            return f"Unknown Model ({model['deviceType']}, {model['deviceVariant']})"

        return model_information.model

    async def is_charging(self) -> bool:
        """Get the mower charging status"""
        if await self.command("IsCharging"):
            return True
        else:
            return False

    async def battery_level(self) -> int | None:
        """Query the mower battery level"""
        return await self.command("GetBatteryLevel")

    async def mower_state(self) -> MowerState | None:
        """Query the mower state"""
        state = await self.command("GetState")
        if state is None:
            return None
        return MowerState(state)

    async def mower_next_start_time(self) -> datetime | None:
        """Query the mower next start time"""
        next_start_time = await self.command("GetNextStartTime")
        if next_start_time is None or next_start_time == 0:
            return None
        return datetime.fromtimestamp(next_start_time, timezone.utc)

    async def mower_activity(self) -> MowerActivity | None:
        """Query the mower activity"""
        activity = await self.command("GetActivity")
        if activity is None:
            return None
        return MowerActivity(activity)

    async def mower_override(self, duration_hours: float = 3.0) -> None:
        """
        Force the mower to run for the specified duration in hours.
        """
        if duration_hours <= 0:
            raise ValueError("Duration must be greater than 0")

        # Set mode of operation to auto:
        await self.command("SetMode", mode=ModeOfOperation.AUTO)

        # Set the duration of operation:
        await self.command("SetOverrideMow", duration=int(duration_hours * 3600))

        # Request trigger to start, the response validation is expected to fail
        await self.command("StartTrigger")

    async def mower_pause(self):
        await self.command("Pause")

    async def mower_resume(self):
        # The response validation is expected to fail
        await self.command("StartTrigger")

    async def mower_park(self):
        await self.command("SetOverrideParkUntilNextStart")

        # Request trigger to start, the response validation is expected to fail
        await self.command("StartTrigger")

    async def get_task(self, taskid: int) -> TaskInformation | None:
        """
        Get information about a specific task
        """
        task = await self.command("GetTask", taskId=taskid)
        if task is None:
            return None
        return TaskInformation(
            task["start"],
            task["duration"],
            task["useOnMonday"],
            task["useOnTuesday"],
            task["useOnWednesday"],
            task["useOnThursday"],
            task["useOnFriday"],
            task["useOnSaturday"],
            task["useOnSunday"],
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
    print("Mower manufacturer: " + (manufacturer or "Unknown manufacturer"))

    model = await mower.get_model()
    print("Mower model: " + (model or "Unknown model"))

    charging = await mower.is_charging()
    if charging:
        print("Mower is charging")
    else:
        print("Mower is not charging")

    battery_level = await mower.battery_level()
    print("Battery is: " + str(battery_level) + "%")

    state = await mower.mower_state()
    if state is not None:
        print("Mower state: " + state.name)

    activity = await mower.mower_activity()
    if activity is not None:
        print("Mower activity: " + activity.name)

    next_start_time = await mower.mower_next_start_time()
    if next_start_time:
        print("Next start time: " + next_start_time.strftime("%Y-%m-%d %H:%M:%S"))
    else:
        print("No next start time")

    statuses = await mower.command("GetAllStatistics")
    for status, value in statuses.items():
        print(status, value)

    serial_number = await mower.command("GetSerialNumber")
    print("Serial number: " + str(serial_number))

    mower_name = await mower.command("GetUserMowerNameAsAsciiString")
    print("Mower name: " + mower_name)

    # print("Running for 3 hours")
    # await mower.mower_override()

    # print("Pause")
    # await mower.mower_pause()

    # print("Resume")
    # await mower.mower_resume()

    # activity = await mower.mower_activity()
    # print("Mower activity: " + activity)

    # If command argument passed then send command
    if args.command:
        print("Sending command to control mower (" + args.command + ")")
        match args.command:
            case "park":
                print("command=park")
                cmd_result = await mower.mower_park()
            case "pause":
                print("command=pause")
                cmd_result = await mower.mower_pause()
            case "resume":
                print("command=resume")
                cmd_result = await mower.mower_resume()
            case "override":
                print("command=override")
                cmd_result = await mower.mower_override()  # type: ignore[func-returns-value]
            case _:
                print("command=??? (Unknown command: " + args.command + ")")
        print("command result = " + str(cmd_result))

    # moved last message after command, this seems to cause all future commands/queries to fail
    last_message = await mower.command("GetMessage", messageId=0)
    print("Last message: ")
    print(
        "\t"
        + datetime.fromtimestamp(last_message["time"], timezone.utc).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    )
    print("\t" + ErrorCodes(last_message["code"]).name)

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

    parser.add_argument(
        "--command",
        metavar="<command>",
        default=None,
        help="Send command to control mower (one of resume, pause, park or override)",
    )

    args = parser.parse_args()

    mower = Mower(1197489078, args.address, args.pin)

    log_level = logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)-15s %(name)-8s %(levelname)s: %(message)s",
    )

    asyncio.run(main(mower))
