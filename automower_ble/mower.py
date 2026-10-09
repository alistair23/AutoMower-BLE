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
from automower_ble.timestamps import local_timestamp

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
        self._schedule_write_uncertain = False

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
            logger.warning("Response failed validation for %s", command_name)

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
        return local_timestamp(
            next_start_time, timezone or dt.datetime.now().astimezone().tzinfo
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

    async def mower_pause(self) -> ResponseResult:
        """Pause and return the checked device result to the caller."""
        result, _ = await self.command_response("Pause")
        return result

    async def mower_resume(self) -> ResponseResult:
        """Resume and return the checked result, without retrying the command."""
        async with self.lock:
            return await self._start_trigger_locked(
                "resume",
                (
                    MowerActivity.GOING_OUT,
                    MowerActivity.MOWING,
                    MowerActivity.GOING_HOME,
                ),
            )

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
            state_result, state = await self.command_response_locked(
                "GetState", warn_on_error=False
            )
            activity_result, activity = await self.command_response_locked(
                "GetActivity", warn_on_error=False
            )
            if (
                state_result is ResponseResult.OK
                and activity_result is ResponseResult.OK
                and state == MowerState.IN_OPERATION
                and activity in accepted_activities
            ):
                logger.debug(
                    "StartTrigger returned UNKNOWN_ERROR but mower accepted %s",
                    context,
                )
                return ResponseResult.OK

        logger.warning(
            "StartTrigger returned %s while starting %s", result.name, context
        )
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

    @staticmethod
    def _schedule_key(task: TaskInformation) -> tuple[int, ...]:
        """Validate fields before any destructive schedule operation."""
        start, duration = task.start_time_in_minutes, task.duration_in_minutes
        if type(start) is not int or not 0 <= start < MINUTES_PER_DAY:
            raise ValueError("Schedule start must be an integer minute within one day")
        if type(duration) is not int or not 0 < duration <= MINUTES_PER_DAY:
            raise ValueError("Schedule duration must be 1–1440 integer minutes")
        days = (
            task.on_monday,
            task.on_tuesday,
            task.on_wednesday,
            task.on_thursday,
            task.on_friday,
            task.on_saturday,
            task.on_sunday,
        )
        if any(type(day) not in (int, bool) or day not in (0, 1) for day in days):
            raise ValueError("Invalid schedule weekday flags")
        return (start, duration, *map(int, days))

    @staticmethod
    def _validate_schedule_seconds(start: int, duration: int) -> None:
        if (
            type(start) is not int
            or type(duration) is not int
            or not 0 <= start < MINUTES_PER_DAY * SECONDS_PER_MINUTE
            or not 0 < duration <= MINUTES_PER_DAY * SECONDS_PER_MINUTE
            or start % SECONDS_PER_MINUTE
            or duration % SECONDS_PER_MINUTE
        ):
            raise ValueError("Schedule time cannot be represented in whole minutes")

    async def _get_tasks_locked(self) -> list[TaskInformation]:
        result, count = await self._calendar_command_locked(
            "GetNumberOfTasks", warn_on_error=False
        )
        if (
            result is not ResponseResult.OK
            or type(count) is not int
            or not 0 <= count <= MAX_SCHEDULE_TASKS
        ):
            raise RuntimeError(f"Unable to read schedule count: {result.name}")
        tasks = []
        first_id = 0
        for index in range(count):
            result, data = await self._calendar_command_locked(
                "GetTask", warn_on_error=False, taskId=index + first_id
            )
            if index == 0 and result is ResponseResult.INVALID_ID:
                first_id = 1
                result, data = await self._calendar_command_locked(
                    "GetTask", warn_on_error=False, taskId=1
                )
            if result is not ResponseResult.OK or not isinstance(data, dict):
                raise RuntimeError(
                    f"Unable to read schedule {index + 1}: {result.name}"
                )
            try:
                start, duration = data["start"], data["duration"]
                self._validate_schedule_seconds(start, duration)
                task = TaskInformation(
                    start // SECONDS_PER_MINUTE,
                    duration // SECONDS_PER_MINUTE,
                    *(
                        data[f"useOn{day}"]
                        for day in (
                            "Monday",
                            "Tuesday",
                            "Wednesday",
                            "Thursday",
                            "Friday",
                            "Saturday",
                            "Sunday",
                        )
                    ),
                )
                self._schedule_key(task)
            except (KeyError, TypeError, ValueError) as err:
                raise RuntimeError(f"Invalid schedule {index + 1}: {err}") from err
            tasks.append(task)
        return tasks

    async def get_tasks(self) -> list[TaskInformation]:
        """Read the complete calendar; failures must not look like an empty one."""
        async with self.lock:
            return await self._get_tasks_locked()

    async def set_tasks(
        self,
        tasks: list[TaskInformation],
        *,
        expected: list[TaskInformation] | None = None,
    ) -> None:
        """Replace schedules without changing mode or starting the mower.

        An uncertain write blocks subsequent replacements on this instance.
        Verify the calendar in the app before creating a fresh client to retry.
        """
        tasks = list(tasks)
        if len(tasks) > MAX_SCHEDULE_TASKS:
            raise ValueError(
                f"A maximum of {MAX_SCHEDULE_TASKS} schedule tasks is supported"
            )
        requested = [self._schedule_key(task) for task in tasks]
        expected_keys = (
            None if expected is None else [self._schedule_key(t) for t in expected]
        )
        async with self.lock:
            if self._schedule_write_uncertain:
                raise RuntimeError(
                    "Previous schedule write is uncertain; verify in the app before using a fresh client"
                )
            current = [self._schedule_key(t) for t in await self._get_tasks_locked()]
            if expected_keys is not None and sorted(current) != sorted(expected_keys):
                raise RuntimeError("Schedules changed while editing; refresh and retry")
            if sorted(current) == sorted(requested):
                return
            self._schedule_write_uncertain = True
            await self._expect_ok_locked("StartTaskTransaction")
            await self._expect_ok_locked("DeleteAllTask")
            for start, duration, *days in requested:
                await self._expect_ok_locked(
                    "AddTask",
                    start=start * SECONDS_PER_MINUTE,
                    duration=duration * SECONDS_PER_MINUTE,
                    **{
                        f"useOn{day}": bool(enabled)
                        for day, enabled in zip(
                            (
                                "Monday",
                                "Tuesday",
                                "Wednesday",
                                "Thursday",
                                "Friday",
                                "Saturday",
                                "Sunday",
                            ),
                            days,
                            strict=True,
                        )
                    },
                    unknown=0,
                )
            await self._expect_ok_locked("CommitTaskTransaction")
            actual = [self._schedule_key(t) for t in await self._get_tasks_locked()]
            if sorted(actual) != sorted(requested):
                raise RuntimeError("Schedule read-back did not match requested changes")
            self._schedule_write_uncertain = False

    async def clear_tasks(self) -> None:
        """Clear through the same guarded and verified replacement path."""
        await self.set_tasks([])

    async def _calendar_command_locked(self, command_name: str, **kwargs):
        response = await self.command_response_locked(command_name, **kwargs)
        # The current upstream transport consumes cancellation; do not continue
        # a calendar transaction if a caller has cancelled this task.
        task = asyncio.current_task()
        if task is not None and task.cancelling():
            raise asyncio.CancelledError
        return response

    async def _expect_ok_locked(self, command_name: str, **kwargs) -> None:
        result, _ = await self._calendar_command_locked(command_name, **kwargs)
        if result is not ResponseResult.OK:
            raise RuntimeError(f"{command_name} returned {result.name}")

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
