"""
The top level script to connect and communicate with the mower
This sends requests and decodes responses. This is an example of
how the request and response classes can be used.
"""

# Copyright: Alistair Francis <alistair@alistair23.me>

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

logger = logging.getLogger(__name__)


class Mower(BLEClient):
    def __init__(self, channel_id: int, address, pin=None):
        super().__init__(channel_id, address, pin)

    async def command(self, command_name: str, **kwargs):
        """
        This function is used to simplify the communication of the mower using the commands found in protocol.json.
        It will send a request to the mower and then wait for a response. The response will be parsed and returned to the caller.
        """
        command = Command(self.channel_id, self.protocol[command_name])
        request = command.generate_request(**kwargs)
        response = await self._request_response(request)
        if response is None:
            return None

        if command.validate_response(response) is False:
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
