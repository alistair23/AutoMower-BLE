"""Strict, serialized schedule reads and writes; never start a mower on edit."""

from automower_ble.protocol import ResponseResult, TaskInformation

DAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


def task_key(task):
    return (
        task.start_time_in_minutes,
        task.duration_in_minutes,
        *(bool(getattr(task, f"on_{day.lower()}")) for day in DAYS),
    )


def validate_tasks(tasks, capabilities):
    limit = capabilities.schedule_limit
    if limit is None:
        raise ValueError("Schedule editing requires a confirmed mower generation")
    if len(tasks) > limit:
        raise ValueError(f"This mower supports at most {limit} schedules")
    if not tasks and capabilities.generation == 3:
        raise ValueError(
            "Generation 3 cannot delete its last schedule; disable its days in the app"
        )
    per_day = [0] * 7
    for task in tasks:
        raw_days = [getattr(task, f"on_{day.lower()}") for day in DAYS]
        if any(type(day) not in (int, bool) or day not in (0, 1) for day in raw_days):
            raise ValueError("Invalid schedule weekday flags")
        start, duration, *days = task_key(task)
        if type(start) is not int or not 0 <= start < 1440:
            raise ValueError("Schedule start must be an integer minute within one day")
        if type(duration) is not int or not 0 < duration <= 1440:
            raise ValueError("Schedule duration must be 1–1440 minutes")
        for index, enabled in enumerate(days):
            per_day[index] += enabled
    if capabilities.generation == 3 and any(count > 2 for count in per_day):
        raise ValueError("Generation 3 supports at most two schedules per day")


def decode_task(data):
    start, duration = data["start"], data["duration"]
    days = [data[f"useOn{day}"] for day in DAYS]
    if (
        type(start) is not int
        or type(duration) is not int
        or not 0 <= start < 86400
        or not 0 < duration <= 86400
        or start % 60
        or duration % 60
    ):
        raise ValueError("Schedule must be losslessly representable in whole minutes")
    if any(type(day) not in (int, bool) or day not in (0, 1) for day in days):
        raise ValueError("Invalid weekday")
    return TaskInformation(start // 60, duration // 60, *map(bool, days))


class ScheduleMixin:
    """Use the upstream transport while propagating every schedule failure."""

    async def get_tasks(self):
        async with self.lock:
            result, count = await self.command_response(
                "GetNumberOfTasks", warn_on_error=False
            )
            if (
                result is not ResponseResult.OK
                or type(count) is not int
                or not 0 <= count <= 15
            ):
                raise RuntimeError(f"Unable to read schedule count: {result.name}")
            if count == 0:
                return []
            tasks = []
            first_id = 0
            for index in range(count):
                result, data = await self.command_response(
                    "GetTask", warn_on_error=False, taskId=index + first_id
                )
                # Retain upstream's 1-based compatibility only on a rejected first ID;
                # never reinterpret a transient or partial read as an empty calendar.
                if index == 0 and result is ResponseResult.INVALID_ID:
                    first_id = 1
                    result, data = await self.command_response(
                        "GetTask", warn_on_error=False, taskId=1
                    )
                if result is not ResponseResult.OK or not isinstance(data, dict):
                    raise RuntimeError(
                        f"Unable to read schedule {index + 1}: {result.name}"
                    )
                try:
                    tasks.append(decode_task(data))
                except (KeyError, TypeError, ValueError) as err:
                    raise RuntimeError(f"Invalid schedule {index + 1}: {err}") from err
            return tasks

    async def set_tasks(self, tasks, *, expected=None):
        tasks = list(tasks)
        validate_tasks(tasks, self.capabilities)
        tasks = [TaskInformation(*task_key(task)) for task in tasks]
        async with self.lock:
            if getattr(self, "_schedule_write_uncertain", False):
                raise RuntimeError(
                    "A previous schedule write failed; verify schedules in the app and reload before retrying"
                )
            current = await self.get_tasks()
            if expected is not None and [task_key(t) for t in current] != [
                task_key(t) for t in expected
            ]:
                raise RuntimeError("Schedules changed while editing; refresh and retry")
            if [task_key(t) for t in current] == [task_key(t) for t in tasks]:
                return
            # Do not send mode, override, resume, or start commands here.
            self._schedule_write_uncertain = True
            await self._expect_ok("StartTaskTransaction")
            await self._expect_ok("DeleteAllTask")
            for task in tasks:
                values = {
                    "start": task.start_time_in_minutes * 60,
                    "duration": task.duration_in_minutes * 60,
                    **{
                        f"useOn{day}": bool(getattr(task, f"on_{day.lower()}"))
                        for day in DAYS
                    },
                }
                await self._expect_ok("AddTask", **values)
            await self._expect_ok("CommitTaskTransaction")
            actual = await self.get_tasks()
            if sorted(task_key(t) for t in actual) != sorted(
                task_key(t) for t in tasks
            ):
                raise RuntimeError(
                    "Schedule read-back did not match the requested changes"
                )
            self._schedule_write_uncertain = False

    async def clear_tasks(self):
        await self.set_tasks([])
