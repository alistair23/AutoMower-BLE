"""Calendar failures never become empty schedules or movement commands."""

import asyncio
import unittest

import pytest
from unittest.mock import AsyncMock

from automower_ble.protocol import Command, ResponseResult, TaskInformation
from automower_ble.gardena import GardenaMower as Mower
from automower_ble.gardena.model_capabilities import identify_model
from automower_ble.gardena.schedule import DAYS, task_key, validate_tasks
from automower_ble.gardena.settings_protocol import corrected_protocol


def model(device_type):
    return identify_model({"deviceType": device_type, "deviceVariant": 1}, "41.00")


def task(start=480, duration=60, day=0):
    return TaskInformation(start, duration, *(index == day for index in range(7)))


def raw_task(value):
    start, duration, *days = task_key(value)
    return dict(
        start=start * 60,
        duration=duration * 60,
        **{f"useOn{day}": enabled for day, enabled in zip(DAYS, days, strict=True)},
    )


class ScheduleTests(unittest.IsolatedAsyncioTestCase):
    def mower(self, tasks=(), device_type=29, fail=None):
        mower = Mower(1, "00:00:00:00:00:00", 1234)
        mower.capabilities = model(device_type)
        state = {"tasks": list(tasks), "calls": []}

        async def command(name, **kwargs):
            state["calls"].append((name, kwargs))
            if name == fail:
                return ResponseResult.DEVICE_BUSY, None
            if name == "GetNumberOfTasks":
                return ResponseResult.OK, len(state["tasks"])
            if name == "GetTask":
                return ResponseResult.OK, raw_task(state["tasks"][kwargs["taskId"]])
            if name == "StartTaskTransaction":
                state["pending"] = list(state["tasks"])
            elif name == "DeleteAllTask":
                state["pending"] = []
            elif name == "AddTask":
                state["pending"].append(
                    TaskInformation(
                        kwargs["start"] // 60,
                        kwargs["duration"] // 60,
                        *(kwargs[f"useOn{day}"] for day in DAYS),
                    )
                )
            elif name == "CommitTaskTransaction":
                state["tasks"] = state.pop("pending")
            else:
                raise AssertionError(f"Unexpected command: {name}")
            return ResponseResult.OK, None

        mower.command_response = AsyncMock(side_effect=command)
        return mower, state

    async def test_empty_and_failed_counts_are_distinct(self):
        mower, _ = self.mower()
        self.assertEqual(await mower.get_tasks(), [])
        for result, count in (
            (ResponseResult.DEVICE_BUSY, None),
            (ResponseResult.OK, None),
            (ResponseResult.OK, -1),
            (ResponseResult.OK, True),
        ):
            mower.command_response = AsyncMock(return_value=(result, count))
            with pytest.raises(RuntimeError):
                await mower.get_tasks()

    async def test_partial_read_aborts_without_writes(self):
        mower, state = self.mower([task()], fail="GetTask")
        with pytest.raises(RuntimeError):
            await mower.set_tasks([task(600)])
        self.assertEqual(
            [name for name, _ in state["calls"]], ["GetNumberOfTasks", "GetTask"]
        )

    async def test_edit_preserves_parking_and_reads_back(self):
        mower, state = self.mower([task()])
        await mower.set_tasks([task(600)], expected=[task()])
        self.assertEqual([task_key(t) for t in state["tasks"]], [task_key(task(600))])
        names = [name for name, _ in state["calls"]]
        self.assertNotIn("SetMode", names)
        self.assertNotIn("ClearOverride", names)
        self.assertNotIn("StartTrigger", names)
        self.assertEqual(names[-2:], ["GetNumberOfTasks", "GetTask"])

    async def test_concurrent_edit_is_rejected_before_replacement(self):
        mower, state = self.mower([task()])
        results = await asyncio.gather(
            mower.set_tasks([task(600)], expected=[task()]),
            mower.set_tasks([task(700)], expected=[task()]),
            return_exceptions=True,
        )
        self.assertEqual(sum(isinstance(result, RuntimeError) for result in results), 1)
        self.assertEqual(
            sum(name == "StartTaskTransaction" for name, _ in state["calls"]), 1
        )

    async def test_transaction_failure_blocks_automatic_retry(self):
        for fail in (
            "StartTaskTransaction",
            "DeleteAllTask",
            "AddTask",
            "CommitTaskTransaction",
        ):
            mower, state = self.mower([task()], fail=fail)
            with pytest.raises(RuntimeError):
                await mower.set_tasks([task(600)])
            count = len(state["calls"])
            with pytest.raises(RuntimeError, match="previous schedule write failed"):
                await mower.set_tasks([task(600)])
            self.assertEqual(len(state["calls"]), count)
            self.assertEqual([task_key(t) for t in state["tasks"]], [task_key(task())])

    async def test_cancelled_write_blocks_retry_without_committing(self):
        mower, state = self.mower([task()])
        original = mower.command_response.side_effect

        async def cancelled(name, **kwargs):
            if name == "AddTask":
                raise asyncio.CancelledError
            return await original(name, **kwargs)

        mower.command_response.side_effect = cancelled
        with pytest.raises(asyncio.CancelledError):
            await mower.set_tasks([task(600)])
        self.assertNotIn("CommitTaskTransaction", [name for name, _ in state["calls"]])
        count = mower.command_response.await_count
        with pytest.raises(RuntimeError, match="previous schedule write failed"):
            await mower.set_tasks([task(600)])
        self.assertEqual(mower.command_response.await_count, count)

    async def test_readback_mismatch_blocks_retry(self):
        mower, state = self.mower([task()])
        original = mower.command_response.side_effect

        async def mismatched(name, **kwargs):
            result = await original(name, **kwargs)
            if name == "CommitTaskTransaction":
                state["tasks"] = [task(700)]
            return result

        mower.command_response.side_effect = mismatched
        with pytest.raises(RuntimeError, match="read-back did not match"):
            await mower.set_tasks([task(600)])
        count = mower.command_response.await_count
        with pytest.raises(RuntimeError, match="previous schedule write failed"):
            await mower.set_tasks([task(600)])
        self.assertEqual(mower.command_response.await_count, count)

    async def test_one_based_fallback_only_for_rejected_first_index(self):
        mower, _ = self.mower()
        mower.command_response = AsyncMock(
            side_effect=[
                (ResponseResult.OK, 1),
                (ResponseResult.INVALID_ID, None),
                (ResponseResult.OK, raw_task(task())),
            ]
        )
        self.assertEqual(
            [task_key(t) for t in await mower.get_tasks()], [task_key(task())]
        )
        self.assertEqual(mower.command_response.await_args_list[-1].kwargs["taskId"], 1)

    def test_model_capacity_and_g3_last_entry(self):
        for tasks in (
            [],
            [task(day=i % 7) for i in range(15)],
            [task(), task(600), task(700)],
        ):
            with pytest.raises(
                ValueError, match="last schedule|at most|two schedules|confirmed"
            ):
                validate_tasks(tasks, model(14))
        validate_tasks([task(day=i % 7) for i in range(14)], model(14))
        validate_tasks([], model(29))
        validate_tasks([task() for _ in range(15)], model(29))
        with pytest.raises(
            ValueError, match="last schedule|at most|two schedules|confirmed"
        ):
            validate_tasks([task()], model(99))

    def test_app_add_task_wire_layout(self):
        for device_type in (14, 29, 43):
            spec = corrected_protocol({}, model(device_type))["AddTask"]
            request = Command(1, spec).generate_request(**raw_task(task()))
            self.assertEqual((spec["major"], spec["minor"]), (4690, 7))
            self.assertEqual(request[16], 15)
            self.assertEqual(len(request[18:-2]), 15)
            self.assertEqual(request[26:-2], bytes((1, 0, 0, 0, 0, 0, 0)))

    async def test_malformed_and_nonminute_times_rejected(self):
        for invalid in ({"start": 30}, {"duration": 61}, {"useOnMonday": 2}):
            mower, _ = self.mower()
            mower.command_response = AsyncMock(
                side_effect=[
                    (ResponseResult.OK, 1),
                    (ResponseResult.OK, raw_task(task()) | invalid),
                ]
            )
            with pytest.raises(RuntimeError):
                await mower.get_tasks()
