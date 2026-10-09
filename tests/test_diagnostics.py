"""Read-only diagnostic wire layouts and independent statistics failures."""

import asyncio
import json
import unittest
from importlib.resources import files
from unittest.mock import AsyncMock, patch

import pytest
from bleak import BleakError

from automower_ble.helpers import crc
from automower_ble.mower import Mower
from automower_ble.protocol import Command, ResponseResult


@pytest.fixture
def protocol():
    return json.loads(files("automower_ble").joinpath("protocol.json").read_text())


def response_frame(group, minor, payload):
    """Build a synthetic response from literal IDs, not the protocol dictionary."""
    frame = bytearray.fromhex("02fd0000b63b6047010001af00000000000000")
    frame[12:16] = group.to_bytes(2, "little") + minor.to_bytes(2, "little")
    frame[17:19] = len(payload).to_bytes(2, "little")
    frame.extend(payload)
    frame.extend(b"\x00\x03")
    frame[2:4] = (len(frame) - 4).to_bytes(2, "little")
    frame[9] = crc(frame, 1, 8)
    frame[-2] = crc(frame, 1, len(frame) - 3)
    return frame


@pytest.mark.parametrize(("front", "rear"), [(0, 0), (0, 1), (1, 0), (1, 1)])
def test_collision_is_two_status_fields_not_accessory_mask(protocol, front, rear):
    command = Command(1197489078, protocol["GetCollisionSensorStatus"])
    assert command.generate_request()[12:18] == bytes.fromhex("461008000000")
    frame = response_frame(4166, 8, bytes([front, rear]))
    assert command.validate_command_response(frame)
    assert command.parse_response(frame) == {"front": front, "rear": rear}
    assert "GetSupportedAccessories" not in protocol


@pytest.mark.parametrize("lifted", [0, 1])
def test_lift_status_packet(protocol, lifted):
    command = Command(1197489078, protocol["GetLiftSensorStatus"])
    assert command.generate_request()[12:18] == bytes.fromhex("7c1106000000")
    frame = response_frame(4476, 6, bytes([lifted]))
    assert command.validate_command_response(frame)
    assert command.parse_response(frame)["response"] == lifted


@pytest.mark.parametrize(
    ("name", "minor"),
    [
        ("GetTotalRunningTime", 1),
        ("GetTotalCuttingTime", 2),
        ("GetTotalChargingTime", 3),
        ("GetTotalSearchingTime", 4),
        ("GetNumberOfCollisions", 5),
        ("GetNumberOfChargingCycles", 6),
    ],
)
@pytest.mark.parametrize("value", [0, 3600, 0xFFFFFFFF])
def test_individual_statistics_wire_layout(protocol, name, minor, value):
    command = Command(1197489078, protocol[name])
    assert command.generate_request()[12:18] == b"\x76\x12" + bytes([minor, 0, 0, 0])
    frame = response_frame(4726, minor, value.to_bytes(4, "little"))
    assert command.validate_command_response(frame)
    assert command.parse_response(frame)["response"] == value


class StatisticsTests(unittest.IsolatedAsyncioTestCase):
    async def test_independent_counters_and_no_aggregate_or_writes(self):
        mower = Mower(1, "00:00:00:00:00:00")
        with patch.object(mower, "command_response", new_callable=AsyncMock) as read:
            read.side_effect = [(ResponseResult.OK, value) for value in range(6)]
            result = await mower.mower_statistics()
            assert list(result.values()) == list(range(6))
            assert [c.args[0] for c in read.await_args_list] == [
                "GetTotalRunningTime",
                "GetTotalCuttingTime",
                "GetTotalChargingTime",
                "GetTotalSearchingTime",
                "GetNumberOfCollisions",
                "GetNumberOfChargingCycles",
            ]
            assert all(
                c.kwargs == {"warn_on_error": False} for c in read.await_args_list
            )

    async def test_failed_or_invalid_field_does_not_hide_other_counters(self):
        failures = [
            (result, 123)
            for result in ResponseResult
            if result is not ResponseResult.OK
        ]
        failures.extend(
            (ResponseResult.OK, value)
            for value in (None, True, -1, 1.5, "7", {}, 0x100000000)
        )
        mower = Mower(1, "00:00:00:00:00:00")
        for failure in failures:
            for index in range(6):
                with (
                    self.subTest(failure=failure, index=index),
                    patch.object(
                        mower, "command_response", new_callable=AsyncMock
                    ) as read,
                ):
                    replies = [(ResponseResult.OK, 42)] * 6
                    replies[index] = failure
                    read.side_effect = replies
                    values = list((await mower.mower_statistics()).values())
                    expected = [42] * 6
                    expected[index] = None
                    assert values == expected
                    assert read.await_count == 6

    async def test_next_call_retries_transient_read(self):
        mower = Mower(1, "00:00:00:00:00:00")
        with patch.object(mower, "command_response", new_callable=AsyncMock) as read:
            read.return_value = ResponseResult.DEVICE_BUSY, None
            assert all(v is None for v in (await mower.mower_statistics()).values())
            read.return_value = ResponseResult.OK, 0
            assert all(v == 0 for v in (await mower.mower_statistics()).values())
            assert read.await_count == 12

    async def test_transport_errors_and_cancellation_are_not_hidden(self):
        mower = Mower(1, "00:00:00:00:00:00")
        for error in (
            BleakError("disconnected"),
            TimeoutError(),
            asyncio.CancelledError(),
        ):
            with patch.object(
                mower, "command_response", new_callable=AsyncMock
            ) as read:
                read.side_effect = error
                with pytest.raises(type(error)):
                    await mower.mower_statistics()
                assert read.await_count == 1
