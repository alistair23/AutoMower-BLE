"""Exercise real calendar locking and failure paths with a read/write fake."""

import asyncio
import unittest
from unittest.mock import AsyncMock, patch

import pytest

from automower_ble.mower import Mower
from automower_ble.protocol import (
    MowerActivity,
    MowerState,
    ResponseResult,
    TaskInformation,
)

DAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


def task(start=60):
    return TaskInformation(start, 30, True, False, False, False, False, False, False)


def wire(value):
    return {
        "start": value.start_time_in_minutes * 60,
        "duration": value.duration_in_minutes * 60,
        **{f"useOn{day}": int(getattr(value, f"on_{day.lower()}")) for day in DAYS},
    }


class CalendarTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.mower = Mower(1, "00:00:00:00:00:00")
        self.calendar = [wire(task())]
        self.pending = []
        self.calls = []
        self.failure = None
        self.mismatch = False
        self.mower.command_response_locked = self.reply

    async def reply(self, command, **kwargs):
        assert self.mower.lock.locked()
        await asyncio.sleep(0)
        self.calls.append(command)
        if command == self.failure:
            return ResponseResult.DEVICE_BUSY, None
        if command == "GetNumberOfTasks":
            return ResponseResult.OK, len(self.calendar)
        if command == "GetTask":
            return ResponseResult.OK, self.calendar[kwargs["taskId"]]
        if command == "DeleteAllTask":
            self.pending = []
        if command == "AddTask":
            self.pending.append({k: v for k, v in kwargs.items() if k != "unknown"})
        if command == "CommitTaskTransaction" and not self.mismatch:
            self.calendar = self.pending.copy()
        return ResponseResult.OK, None

    async def test_replace_preserves_mode_and_reads_back(self):
        await self.mower.set_tasks([task(120)], expected=[task()])
        assert self.calls == [
            "GetNumberOfTasks",
            "GetTask",
            "StartTaskTransaction",
            "DeleteAllTask",
            "AddTask",
            "CommitTaskTransaction",
            "GetNumberOfTasks",
            "GetTask",
        ]
        assert self.calendar == [wire(task(120))]
        assert not self.mower._schedule_write_uncertain

    async def test_clear_uses_guarded_path_and_no_start(self):
        await self.mower.clear_tasks()
        assert self.calendar == []
        assert self.calls == [
            "GetNumberOfTasks",
            "GetTask",
            "StartTaskTransaction",
            "DeleteAllTask",
            "CommitTaskTransaction",
            "GetNumberOfTasks",
        ]

    async def test_noop_and_stale_expected_never_write(self):
        await self.mower.set_tasks([task()])
        with pytest.raises(RuntimeError, match="changed while editing"):
            await self.mower.set_tasks([task(120)], expected=[])
        assert all(c.startswith("Get") for c in self.calls)

    async def test_failed_reads_never_become_empty_or_allow_writes(self):
        for command in ("GetNumberOfTasks", "GetTask"):
            self.failure = command
            self.calls.clear()
            with pytest.raises(RuntimeError):
                await self.mower.set_tasks([task(120)])
            assert all(c.startswith("Get") for c in self.calls)
            assert not self.mower._schedule_write_uncertain

    async def test_each_failed_write_stops_and_blocks_replay(self):
        writes = [
            "StartTaskTransaction",
            "DeleteAllTask",
            "AddTask",
            "CommitTaskTransaction",
        ]
        for command in writes:
            self.mower._schedule_write_uncertain = False
            self.calls.clear()
            self.failure = command
            with pytest.raises(RuntimeError, match=command):
                await self.mower.set_tasks([task(120)])
            assert self.calls[-1] == command
            count = len(self.calls)
            with pytest.raises(RuntimeError, match="uncertain"):
                await self.mower.clear_tasks()
            assert len(self.calls) == count
            assert not self.mower.lock.locked()

    async def test_readback_mismatch_blocks_replay(self):
        self.mismatch = True
        with pytest.raises(RuntimeError, match="read-back"):
            await self.mower.set_tasks([task(120)])
        assert self.mower._schedule_write_uncertain

    async def test_validation_happens_before_any_command(self):
        invalid = [task(-1), task(1440), task(1.5), task(True)]
        bad_days = task()
        bad_days.on_monday = "false"
        invalid.append(bad_days)
        for value in invalid:
            with pytest.raises(ValueError, match="Schedule|Invalid"):
                await self.mower.set_tasks([value])
        with pytest.raises(ValueError, match="maximum"):
            await self.mower.set_tasks([task()] * 16)
        assert self.calls == []

    async def test_cancelled_write_keeps_uncertainty_and_releases_lock(self):
        entered = asyncio.Event()

        async def blocking(command, **kwargs):
            if command == "AddTask":
                entered.set()
                await asyncio.Future()
            return await self.reply(command, **kwargs)

        self.mower.command_response_locked = blocking
        pending = asyncio.create_task(self.mower.set_tasks([task(120)]))
        await asyncio.wait_for(entered.wait(), 2)
        pending.cancel()
        with pytest.raises(asyncio.CancelledError):
            await pending
        assert self.mower._schedule_write_uncertain
        assert not self.mower.lock.locked()
        assert "CommitTaskTransaction" not in self.calls

    async def test_concurrent_edits_recheck_expected_under_lock(self):
        results = await asyncio.gather(
            self.mower.set_tasks([task(120)], expected=[task()]),
            self.mower.set_tasks([task(180)], expected=[task()]),
            return_exceptions=True,
        )
        assert sum(isinstance(r, RuntimeError) for r in results) == 1
        assert self.calls.count("StartTaskTransaction") == 1

    async def test_swallowed_transport_cancellation_does_not_start_write(self):
        async def swallowed(_command, **_kwargs):
            asyncio.current_task().cancel()
            try:
                await asyncio.sleep(0)
            except asyncio.CancelledError:
                return ResponseResult.OK, 0

        self.mower.command_response_locked = swallowed
        pending = asyncio.create_task(self.mower.set_tasks([task(120)]))
        with pytest.raises(asyncio.CancelledError):
            await pending
        assert not self.mower._schedule_write_uncertain
        assert not self.mower.lock.locked()

    async def test_readback_failure_leaves_write_uncertain(self):
        async def readback_failure(command, **kwargs):
            result = await self.reply(command, **kwargs)
            if command == "CommitTaskTransaction":
                self.failure = "GetNumberOfTasks"
            return result

        self.mower.command_response_locked = readback_failure
        with pytest.raises(RuntimeError, match="schedule count"):
            await self.mower.set_tasks([task(120)])
        assert self.mower._schedule_write_uncertain

    async def test_partial_read_is_not_retried_as_one_based(self):
        with (
            patch.object(
                self.mower,
                "command_response_locked",
                AsyncMock(
                    side_effect=[
                        (ResponseResult.OK, 2),
                        (ResponseResult.OK, wire(task())),
                        (ResponseResult.INVALID_ID, None),
                    ]
                ),
            ) as read,
            pytest.raises(RuntimeError, match="schedule 2"),
        ):
            await self.mower.get_tasks()
        assert read.await_count == 3

    async def test_invalid_counts_and_partial_tasks_raise(self):
        for count in (None, True, -1, 16, "1"):
            with (
                patch.object(
                    self.mower,
                    "command_response_locked",
                    AsyncMock(return_value=(ResponseResult.OK, count)),
                ),
                pytest.raises(RuntimeError),
            ):
                await self.mower.get_tasks()
        for data in (
            {},
            {**wire(task()), "start": 61},
            {**wire(task()), "useOnMonday": 2},
        ):
            with (
                patch.object(
                    self.mower,
                    "command_response_locked",
                    AsyncMock(
                        side_effect=[(ResponseResult.OK, 1), (ResponseResult.OK, data)]
                    ),
                ),
                pytest.raises(RuntimeError),
            ):
                await self.mower.get_tasks()

    async def test_one_based_fallback_only_after_invalid_first_id(self):
        with patch.object(
            self.mower,
            "command_response_locked",
            AsyncMock(
                side_effect=[
                    (ResponseResult.OK, 1),
                    (ResponseResult.INVALID_ID, None),
                    (ResponseResult.OK, wire(task())),
                ]
            ),
        ) as read:
            assert len(await self.mower.get_tasks()) == 1
            assert [c.kwargs["taskId"] for c in read.await_args_list[1:]] == [0, 1]


class ActionTests(unittest.IsolatedAsyncioTestCase):
    async def test_pause_returns_checked_reply(self):
        mower = Mower(1, "00:00:00:00:00:00")
        with patch.object(
            mower,
            "command_response",
            AsyncMock(return_value=(ResponseResult.NOT_ALLOWED, None)),
        ) as reply:
            assert await mower.mower_pause() is ResponseResult.NOT_ALLOWED
            reply.assert_awaited_once_with("Pause")

    async def test_resume_verifies_ambiguous_reply_without_replaying(self):
        mower = Mower(1, "00:00:00:00:00:00")
        for status, state, activity, expected in (
            (
                ResponseResult.OK,
                MowerState.IN_OPERATION,
                MowerActivity.GOING_HOME,
                ResponseResult.OK,
            ),
            (
                ResponseResult.DEVICE_BUSY,
                MowerState.IN_OPERATION,
                MowerActivity.MOWING,
                ResponseResult.UNKNOWN_ERROR,
            ),
            (
                ResponseResult.OK,
                MowerState.PAUSED,
                MowerActivity.MOWING,
                ResponseResult.UNKNOWN_ERROR,
            ),
        ):
            with (
                patch.object(
                    mower,
                    "command_response_locked",
                    AsyncMock(
                        side_effect=[
                            (ResponseResult.UNKNOWN_ERROR, None),
                            (status, state),
                            (ResponseResult.OK, activity),
                        ]
                    ),
                ) as read,
                patch("automower_ble.mower.asyncio.sleep", new_callable=AsyncMock),
            ):
                assert await mower.mower_resume() is expected
                assert [c.args[0] for c in read.await_args_list] == [
                    "StartTrigger",
                    "GetState",
                    "GetActivity",
                ]

    async def test_resume_does_not_suppress_explicit_rejection(self):
        mower = Mower(1, "00:00:00:00:00:00")
        with patch.object(
            mower,
            "command_response_locked",
            AsyncMock(return_value=(ResponseResult.NOT_ALLOWED, None)),
        ) as read:
            assert await mower.mower_resume() is ResponseResult.NOT_ALLOWED
            assert read.await_count == 1
