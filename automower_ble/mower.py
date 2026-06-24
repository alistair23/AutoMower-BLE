"""
The top level script to connect and communicate with the mower
This sends requests and decodes responses. This is an example of
how the request and response classes can be used.
"""

# Copyright: Alistair Francis <alistair@alistair23.me>

import argparse
import asyncio
import contextlib
import datetime as dt
import logging

from automower_ble.protocol import (
    BLEClient,
    Command,
    MowerState,
    MowerActivity,
    ModeOfOperation,
    OverrideAction,
    ResponseResult,
    TaskInformation,
)
from automower_ble.models import MowerModels
from automower_ble.error_codes import ErrorCodes

from bleak import BleakScanner

logger = logging.getLogger(__name__)

MAX_SCHEDULE_TASKS = 15
SECONDS_PER_MINUTE = 60
MINUTES_PER_DAY = 24 * 60
SPOT_CUT_DURATION_SECONDS = 30 * SECONDS_PER_MINUTE


class Mower(BLEClient):
    def __init__(self, channel_id: int, address, pin=None):
        super().__init__(channel_id, address, pin)
        self.keep_alive_event = asyncio.Event()
        self.task: asyncio.Task | None = None
        self._connect_lock = asyncio.Lock()

    async def connect(self, device) -> ResponseResult:
        """
        Connect to a device and setup the channel

        Returns a ResponseResult
        """
        if self.is_connected():
            self._ensure_keep_alive()
            return ResponseResult.OK

        async with self._connect_lock:
            if self.is_connected():
                self._ensure_keep_alive()
                return ResponseResult.OK

            status = await super().connect(device)
            if status == ResponseResult.OK:
                self._ensure_keep_alive()
            return status

    def _ensure_keep_alive(self) -> None:
        """Start one keep-alive task for the active mower connection."""
        self.keep_alive_event.clear()
        if self.task is None or self.task.done():
            self.task = asyncio.create_task(self._keep_alive())

    async def disconnect(self):
        """
        Disconnect from the mower, this should be called after every
        `connect()` before the Python script exits
        """
        self.keep_alive_event.set()
        try:
            return await super().disconnect()
        finally:
            if self.task is not None and self.task is not asyncio.current_task():
                self.task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await self.task
                self.task = None

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
                logger.warning("Failed to send keep alive: %s", e)
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
        return response_dict

    async def command_response(
        self, command_name: str, warn_on_error: bool = True, **kwargs
    ):
        """
        Send a command and return the mower response result with parsed data.

        This is useful for command buttons where Home Assistant should surface a
        clear command failure instead of only logging a low-level protocol warning.
        """
        command = Command(self.channel_id, (await self.get_protocol())[command_name])
        request = command.generate_request(**kwargs)
        response = await self._request_response(request)
        if response is None:
            return ResponseResult.UNKNOWN_ERROR, None

        result = ResponseResult(response[16])
        if result is not ResponseResult.OK:
            if warn_on_error:
                logger.warning("%s returned %s", command_name, result.name)
            else:
                logger.debug("%s returned %s", command_name, result.name)
            return result, None

        try:
            response_dict = command.parse_response(response)
        except ValueError as err:
            logger.debug("%s returned unparsable payload: %s", command_name, err)
            return result, None
        if response_dict is not None and len(response_dict) == 1:
            return result, response_dict["response"]
        return result, response_dict

    async def command_response_locked(
        self, command_name: str, warn_on_error: bool = True, **kwargs
    ):
        """Send a command while the caller already holds the BLE command lock."""
        command = Command(self.channel_id, (await self.get_protocol())[command_name])
        request = command.generate_request(**kwargs)
        response = await self._request_response_locked(request)
        if response is None:
            return ResponseResult.UNKNOWN_ERROR, None

        result = ResponseResult(response[16])
        if result is not ResponseResult.OK:
            if warn_on_error:
                logger.warning("%s returned %s", command_name, result.name)
            else:
                logger.debug("%s returned %s", command_name, result.name)
            return result, None

        try:
            response_dict = command.parse_response(response)
        except ValueError as err:
            logger.debug("%s returned unparsable payload: %s", command_name, err)
            return result, None
        if response_dict is not None and len(response_dict) == 1:
            return result, response_dict["response"]
        return result, response_dict

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
        return bool(await self.command("IsCharging"))

    async def battery_level(self) -> int | None:
        """Query the mower battery level"""
        return await self.command("GetBatteryLevel")

    async def mower_state(self) -> MowerState | None:
        """Query the mower state"""
        state = await self.command("GetState")
        if state is None:
            return None
        return MowerState(state)

    async def mower_next_start_time(
        self, timezone: dt.tzinfo | None = None
    ) -> dt.datetime | None:
        """Query the mower next start time"""
        next_start_time = await self.command("GetNextStartTime")
        if next_start_time is None or next_start_time == 0:
            return None
        # The mower reports this value as seconds since epoch in local time, not
        # UTC. Decode the timestamp as a UTC wall-clock value, then attach the
        # desired local timezone so Home Assistant displays the actual schedule.
        local_time = dt.datetime.fromtimestamp(next_start_time, dt.UTC).replace(
            tzinfo=None
        )
        return local_time.replace(
            tzinfo=timezone or dt.datetime.now().astimezone().tzinfo
        )

    async def mower_activity(self) -> MowerActivity | None:
        """Query the mower activity"""
        activity = await self.command("GetActivity")
        if activity is None:
            return None
        return MowerActivity(activity)

    async def mower_mode(self) -> ModeOfOperation | None:
        """Query the mower mode of operation."""
        mode = await self.command("GetMode")
        if mode is None:
            return None
        try:
            return ModeOfOperation(mode)
        except ValueError:
            logger.debug("Unknown mower mode: %s", mode)
            return None

    async def mower_override_status(self) -> dict[str, int | OverrideAction] | None:
        """Query the current mower override status."""
        result, override = await self.command_response(
            "GetOverride", warn_on_error=False
        )
        if result is not ResponseResult.OK or override is None:
            return None

        try:
            action = OverrideAction(override["action"])
        except ValueError:
            logger.debug("Unknown mower override action: %s", override["action"])
            action = OverrideAction.NONE

        return {
            "action": action,
            "startTime": override["startTime"],
            "duration": override["duration"],
            "reserved": override["reserved"],
        }

    @staticmethod
    def is_permanently_parked_state(
        mode: ModeOfOperation | None, override: dict | None
    ) -> bool:
        """Return true if mode/override represent park until further notice."""
        if mode is ModeOfOperation.HOME:
            return True
        return (
            override is not None
            and override.get("action") is OverrideAction.FORCEDPARK
            and override.get("duration") == 0
        )

    async def mower_is_permanently_parked(self) -> bool:
        """Return true if the mower is parked until further notice."""
        mode = await self.mower_mode()
        override = await self.mower_override_status()
        return self.is_permanently_parked_state(mode, override)

    async def mower_resume_schedule(self) -> ResponseResult:
        """Return the mower to scheduled/automatic operation."""
        result, _ = await self.command_response("ClearOverride", warn_on_error=False)
        if result is not ResponseResult.OK:
            logger.debug(
                "ClearOverride returned %s while resuming schedule", result.name
            )

        result, _ = await self.command_response("SetMode", mode=ModeOfOperation.AUTO)
        return result

    async def mower_park_permanently(self) -> ResponseResult:
        """Park the mower until further notice."""
        result, _ = await self.command_response("SetMode", mode=ModeOfOperation.HOME)
        return result

    async def mower_override(self, duration_hours: float = 3.0) -> ResponseResult:
        """
        Force the mower to run for the specified duration in hours.
        """
        if duration_hours <= 0:
            raise ValueError("Duration must be greater than 0")

        async with self.lock:
            result, _ = await self.command_response_locked(
                "ClearOverride", warn_on_error=False
            )
            if result is not ResponseResult.OK:
                logger.debug(
                    "ClearOverride returned %s while starting manual mowing",
                    result.name,
                )

            result, _ = await self.command_response_locked(
                "SetMode", mode=ModeOfOperation.AUTO
            )
            if result is not ResponseResult.OK:
                return result

            result, _ = await self.command_response_locked(
                "SetOverrideMow", duration=int(duration_hours * 3600)
            )
            if result is not ResponseResult.OK:
                return result

            return await self._start_trigger_locked(
                "manual mowing",
                (MowerActivity.GOING_OUT, MowerActivity.MOWING),
            )

    async def mower_pause(self):
        await self.command("Pause")

    async def mower_resume(self):
        # The response validation is expected to fail
        await self.command("StartTrigger")

    async def mower_spot_cut(self) -> ResponseResult:
        """
        Start spot cutting.

        The dedicated StartSpotCutting command is rejected with INVALID_ID on
        some Gardena models. The official app first arms SpotCut, then starts
        a manual mowing override.
        """
        async with self.lock:
            result, _ = await self.command_response_locked("Pause", warn_on_error=False)
            if result is ResponseResult.OK:
                await asyncio.sleep(1)
            elif result not in (
                ResponseResult.UNKNOWN_ERROR,
                ResponseResult.NOT_ALLOWED,
            ):
                logger.debug("Pause returned %s while starting SpotCut", result.name)

            result, _ = await self.command_response_locked(
                "ClearOverride", warn_on_error=False
            )
            if result is not ResponseResult.OK:
                logger.debug(
                    "ClearOverride returned %s while starting SpotCut", result.name
                )

            result, _ = await self.command_response_locked(
                "SetMode", mode=ModeOfOperation.AUTO
            )
            if result is not ResponseResult.OK:
                return result

            result, _ = await self.command_response_locked("PrepareSpotCutting")
            if result is not ResponseResult.OK:
                return result

            result, _ = await self.command_response_locked(
                "SetOverrideMow", duration=SPOT_CUT_DURATION_SECONDS
            )
            if result is not ResponseResult.OK:
                return result

            result, _ = await self.command_response_locked(
                "StartTrigger", warn_on_error=False
            )
            if result is not ResponseResult.OK:
                return await self._start_trigger_result_locked(
                    result,
                    "SpotCut",
                    (MowerActivity.MOWING,),
                )

            return result

    async def _start_trigger_locked(
        self, context: str, accepted_activities: tuple[MowerActivity, ...]
    ) -> ResponseResult:
        """Send StartTrigger and tolerate app-observed successful UNKNOWN_ERROR."""
        result, _ = await self.command_response_locked(
            "StartTrigger", warn_on_error=False
        )
        if result is ResponseResult.OK:
            return result

        return await self._start_trigger_result_locked(
            result,
            context,
            accepted_activities,
        )

    async def _start_trigger_result_locked(
        self,
        result: ResponseResult,
        context: str,
        accepted_activities: tuple[MowerActivity, ...],
    ) -> ResponseResult:
        """Validate a StartTrigger result against the actual mower state."""
        if result is ResponseResult.UNKNOWN_ERROR:
            await asyncio.sleep(2)
            _, state = await self.command_response_locked(
                "GetState", warn_on_error=False
            )
            _, activity = await self.command_response_locked(
                "GetActivity", warn_on_error=False
            )
            if state == MowerState.IN_OPERATION and activity in accepted_activities:
                logger.debug(
                    "StartTrigger returned UNKNOWN_ERROR but mower accepted %s",
                    context,
                )
                return ResponseResult.OK

        logger.warning("StartTrigger returned %s while starting %s", result.name, context)
        return result

    async def mower_stop_spot_cut(self) -> ResponseResult:
        """Stop SpotCut by pausing the mower, matching the app-observed flow."""
        result, _ = await self.command_response("Pause")
        return result

    async def mower_park(self) -> ResponseResult:
        result, task_count = await self.command_response(
            "GetNumberOfTasks", warn_on_error=False
        )
        if result is not ResponseResult.OK:
            return result

        if task_count:
            result, _ = await self.command_response("SetOverrideParkUntilNextStart")
            return result

        return await self.mower_park_permanently()

    async def get_task(self, taskid: int) -> TaskInformation | None:
        """
        Get information about a specific task
        """
        result, task = await self.command_response(
            "GetTask", warn_on_error=False, taskId=taskid
        )
        if result is not ResponseResult.OK or task is None:
            return None
        return TaskInformation(
            task["start"] // SECONDS_PER_MINUTE,
            (task["duration"] + SECONDS_PER_MINUTE - 1) // SECONDS_PER_MINUTE,
            task["useOnMonday"],
            task["useOnTuesday"],
            task["useOnWednesday"],
            task["useOnThursday"],
            task["useOnFriday"],
            task["useOnSaturday"],
            task["useOnSunday"],
        )

    async def get_tasks(self) -> list[TaskInformation]:
        """Get all weekly schedule tasks from the mower."""
        task_count = await self.command("GetNumberOfTasks")
        if task_count is None:
            return []
        logger.debug("Mower reported %s schedule tasks", task_count)

        for first_task_id in (0, 1):
            tasks: list[TaskInformation] = []
            for task_id in range(first_task_id, first_task_id + task_count):
                task = await self.get_task(task_id)
                if task is None:
                    logger.debug("Unable to read schedule task %s", task_id)
                    break
                tasks.append(task)
            if len(tasks) == task_count:
                logger.debug(
                    "Read %s schedule tasks starting at task id %s",
                    len(tasks),
                    first_task_id,
                )
                return tasks

        logger.debug("Unable to read mower schedule tasks")
        return []

    async def set_tasks(self, tasks: list[TaskInformation]) -> None:
        """Replace the weekly schedule tasks on the mower."""
        if len(tasks) > MAX_SCHEDULE_TASKS:
            raise ValueError(
                f"A maximum of {MAX_SCHEDULE_TASKS} schedule tasks is supported"
            )

        for task in tasks:
            if (
                task.start_time_in_minutes < 0
                or task.start_time_in_minutes >= MINUTES_PER_DAY
            ):
                raise ValueError("Schedule start time must be within one day")
            if (
                task.duration_in_minutes <= 0
                or task.duration_in_minutes > MINUTES_PER_DAY
            ):
                raise ValueError(
                    "Schedule duration must be between 1 minute and 24 hours"
                )

        was_permanently_parked = False
        if tasks:
            was_permanently_parked = await self.mower_is_permanently_parked()

        await self._expect_ok("StartTaskTransaction")
        await self._expect_ok("DeleteAllTask")

        for task in tasks:
            logger.debug(
                "Writing schedule task start=%s duration=%s days=%s",
                task.start_time_in_minutes,
                task.duration_in_minutes,
                {
                    "monday": bool(task.on_monday),
                    "tuesday": bool(task.on_tuesday),
                    "wednesday": bool(task.on_wednesday),
                    "thursday": bool(task.on_thursday),
                    "friday": bool(task.on_friday),
                    "saturday": bool(task.on_saturday),
                    "sunday": bool(task.on_sunday),
                },
            )
            await self._expect_ok(
                "AddTask",
                start=int(task.start_time_in_minutes) * SECONDS_PER_MINUTE,
                duration=int(task.duration_in_minutes) * SECONDS_PER_MINUTE,
                useOnMonday=bool(task.on_monday),
                useOnTuesday=bool(task.on_tuesday),
                useOnWednesday=bool(task.on_wednesday),
                useOnThursday=bool(task.on_thursday),
                useOnFriday=bool(task.on_friday),
                useOnSaturday=bool(task.on_saturday),
                useOnSunday=bool(task.on_sunday),
                unknown=0,
            )

        await self._expect_ok("CommitTaskTransaction")
        if tasks and was_permanently_parked:
            result = await self.mower_resume_schedule()
            if result is not ResponseResult.OK:
                raise RuntimeError(f"SetMode returned {result.name}")

    async def clear_tasks(self) -> None:
        """Remove all weekly schedule tasks from the mower."""
        await self._expect_ok("StartTaskTransaction")
        await self._expect_ok("DeleteAllTask")
        await self._expect_ok("CommitTaskTransaction")

    async def _expect_ok(self, command_name: str, **kwargs) -> None:
        """Send a command and raise when the mower rejects it."""
        result, _ = await self.command_response(command_name, **kwargs)
        if result is not ResponseResult.OK:
            raise RuntimeError(f"{command_name} returned {result.name}")


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
        + dt.datetime.fromtimestamp(last_message["time"], dt.UTC).strftime(
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
