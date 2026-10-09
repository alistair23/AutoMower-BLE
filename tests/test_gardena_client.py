"""Opt-in model selection, guarded packets and actions without mower hardware."""

import unittest
from unittest.mock import AsyncMock, patch

import pytest

from automower_ble.gardena import GardenaMower, identify_model
from automower_ble.gardena.model_diagnostics import read_optional
from automower_ble.gardena.schedule import validate_tasks
from automower_ble.mower import Mower
from automower_ble.protocol import (
    Command,
    MowerActivity,
    MowerState,
    ResponseResult,
    TaskInformation,
)


def profile(kind, firmware="41.00", brand=None):
    return identify_model({"deviceType": kind, "deviceVariant": 1}, firmware, brand)


class GardenaTests(unittest.IsolatedAsyncioTestCase):
    def mower(self, kind=29, firmware="41.00", brand=None):
        mower = GardenaMower(1, "00:00:00:00:00:00")
        mower.capabilities = profile(kind, firmware, brand)
        return mower

    async def test_initialize_reads_only_and_unknown_stays_unknown(self):
        mower = self.mower()
        for identity, kind in (
            ({"deviceType": 29, "deviceVariant": 1}, "P005"),
            ({"deviceType": 47, "deviceVariant": 2}, "unknown"),
        ):
            with patch.object(
                mower,
                "command_response",
                AsyncMock(
                    side_effect=[
                        (ResponseResult.OK, identity),
                        (ResponseResult.OK, "41.00"),
                    ]
                ),
            ) as read:
                assert (await mower.initialize_model()).platform == kind
                assert [c.args[0] for c in read.await_args_list] == [
                    "GetModel",
                    "GetSwVersionStringAppl",
                ]
        with patch.object(mower, "command_response", new_callable=AsyncMock) as read:
            assert await mower.get_diagnostics() == {}
            assert await mower.mower_park_permanently() is ResponseResult.NOT_AVAILABLE
            with pytest.raises(ValueError, match="not confirmed"):
                await mower.set_setting("SetEcoModeEnabled", enabled=True)
            read.assert_not_awaited()

    async def test_protocol_overlay_does_not_change_generic_client(self):
        generic = Mower(1, "00:00:00:00:00:00")
        before = await generic.get_protocol()
        snapshot = {k: v.copy() for k, v in before.items()}
        overlay = await self.mower().get_protocol()
        assert overlay["SetAntiCollisionRadarEnabled"]["major"] == 5356
        assert before == snapshot
        assert not hasattr(generic, "capabilities")

    async def test_calendar_payload_is_15_bytes_for_known_profiles(self):
        for kind in (14, 29, 34, 43):
            mower = self.mower(kind)
            command = Command(1, (await mower.get_protocol())["AddTask"])
            request = command.generate_request(
                start=3600,
                duration=1800,
                useOnMonday=True,
                useOnTuesday=False,
                useOnWednesday=False,
                useOnThursday=False,
                useOnFriday=False,
                useOnSaturday=False,
                useOnSunday=False,
            )
            assert request[12:18] == bytes.fromhex("521207000f00")
            assert request[18:-2] == bytes.fromhex("100e00000807000001000000000000")

    async def test_radar_zone_and_frost_have_distinct_wire_groups(self):
        for kind, firmware, zone, corridor in (
            (14, "40.99", 6050, 26),
            (14, "41.00", 5926, 24),
            (29, "41.00", 6050, 26),
        ):
            definitions = await self.mower(kind, firmware).get_protocol()
            for name, group, minor, kwargs in (
                ("SetZoneProtectEnabled", zone, 3, {"enabled": True}),
                ("SetAntiCollisionRadarEnabled", 5356, 3, {"enabled": True}),
                (
                    "SetStartingPointCorridorCut",
                    4706,
                    corridor + 1,
                    {"startingPointId": 1, "corridorCut": True},
                ),
                ("SetFrostSensorEnabledLegacy", 5412, 2, {"enabled": True}),
            ):
                request = Command(1, definitions[name]).generate_request(**kwargs)
                assert request[12:16] == group.to_bytes(2, "little") + minor.to_bytes(
                    2, "little"
                )

    async def test_invalid_setting_writes_never_reach_transport(self):
        mower = self.mower()
        with patch.object(mower, "command_response", new_callable=AsyncMock) as read:
            for command, values in (
                ("SetAntiCollisionRadarEnabled", {"enabled": True}),
                ("SetEcoModeEnabled", {"enabled": "false"}),
                ("SetSensorControlSensitivity", {"sensitivity": True}),
                ("SetStartingPointDistance", {"startingPointId": 4, "distance": 5}),
                ("SetStartingPointDistance", {"startingPointId": 1, "distance": 101}),
                ("SetDrivePastWire", {"distance": 351}),
                ("GenerateLoopSignalLegacy", {}),
                ("SetMode", {"mode": 0}),
            ):
                with pytest.raises(
                    ValueError, match="not confirmed|Boolean|parameters"
                ):
                    await mower.set_setting(command, **values)
            read.assert_not_awaited()

    async def test_radar_requires_runtime_availability(self):
        mower = self.mower(34, brand="gardena")
        for available in (None, False, 2, True):
            with patch.object(
                mower,
                "command_response",
                AsyncMock(
                    side_effect=[
                        (ResponseResult.OK, {"available": available}),
                        (ResponseResult.OK, None),
                    ]
                ),
            ) as read:
                result = await mower.set_setting(
                    "SetAntiCollisionRadarEnabled", enabled=True
                )
                assert result is (
                    ResponseResult.OK
                    if available is True
                    else ResponseResult.NOT_AVAILABLE
                )
                assert read.await_count == (2 if available is True else 1)

    async def test_legacy_frost_read_and_write_are_paired(self):
        mower = self.mower(14, "20.28")
        with patch.object(
            mower,
            "command_response",
            AsyncMock(side_effect=[(ResponseResult.OK, 0), (ResponseResult.OK, None)]),
        ) as read:
            assert (
                await mower.set_setting("SetFrostSensorEnabledLegacy", enabled=True)
                is ResponseResult.OK
            )
            assert [c.args[0] for c in read.await_args_list] == [
                "GetFrostSensorEnabledLegacy",
                "SetFrostSensorEnabledLegacy",
            ]
        with patch.object(
            mower,
            "command_response",
            AsyncMock(return_value=(ResponseResult.DEVICE_BUSY, None)),
        ) as read:
            assert (
                await mower.set_setting("SetFrostSensorEnabledLegacy", enabled=True)
                is ResponseResult.DEVICE_BUSY
            )
            assert read.await_count == 1

    async def test_g3_point_disable_sequence_and_readback(self):
        mower = self.mower(14)
        with patch.object(
            mower,
            "command_response",
            AsyncMock(
                side_effect=[
                    *[(ResponseResult.OK, None)] * 3,
                    (ResponseResult.OK, 0),
                    (ResponseResult.OK, 0),
                    (ResponseResult.OK, 10),
                    (ResponseResult.OK, 2),
                ]
            ),
        ) as read:
            assert (
                await mower.set_setting(
                    "SetStartingPointEnabled", startingPointId=1, enabled=False
                )
                is ResponseResult.OK
            )
            assert [c.args[0] for c in read.await_args_list] == [
                "SetStartingPointEnabled",
                "SetStartingPointProportion",
                "SetStartingPointEnabled",
                "GetStartingPointEnabled",
                "GetStartingPointProportion",
                "GetStartingPointDistance",
                "GetStartingPointWire",
            ]

    async def test_g3_diagnostics_do_not_probe_g4_battery(self):
        mower = self.mower(14)
        with patch.object(
            mower, "command_response", AsyncMock(return_value=(ResponseResult.OK, {}))
        ) as read:
            await mower.get_diagnostics()
            assert [c.args[0] for c in read.await_args_list] == [
                "GetComboardSensorData",
                "GetSignalQuality",
            ]

    async def test_g4_sentinels_and_loop_average(self):
        mower = self.mower()

        async def reply(command, **kwargs):
            if command == "GetLoopSignalStrength":
                return ResponseResult.OK, (20, 80)[kwargs["signalType"]]
            if command == "GetCollisionSensorStatus":
                return ResponseResult.OK, {"front": 0, "rear": 1}
            return ResponseResult.OK, 999999

        with patch.object(mower, "command_response", side_effect=reply):
            result = await mower.get_diagnostics()
            assert result["batteryCurrent"] is None
            assert result["loopSignalStrength"] == 50
            assert result["collision"] is True
            assert result["lift"] is None
            assert "guide2Signal" not in result

    async def test_transient_diagnostics_retry_but_unsupported_are_cached(self):
        mower = self.mower()
        cache = set()
        with patch.object(
            mower,
            "command_response",
            AsyncMock(
                side_effect=[
                    (ResponseResult.DEVICE_BUSY, None),
                    (ResponseResult.OK, 7),
                    (ResponseResult.INVALID_ID, None),
                ]
            ),
        ) as read:
            assert await read_optional(mower, cache, "GetBatteryCurrent") is None
            assert await read_optional(mower, cache, "GetBatteryCurrent") == 7
            assert await read_optional(mower, cache, "GetBatteryCurrent") is None
            assert await read_optional(mower, cache, "GetBatteryCurrent") is None
            assert read.await_count == 3

    async def test_permanent_park_model_sequences_and_confirmation(self):
        for kind, prefix in (
            (14, ["SetMode"]),
            (29, ["SetMode", "ClearOverride"]),
            (34, ["SetMode", "ClearOverride"]),
            (43, ["SetMode", "ClearOverride"]),
        ):
            mower = self.mower(kind)
            with (
                patch.object(
                    mower,
                    "command_response",
                    AsyncMock(
                        side_effect=[
                            *[(ResponseResult.OK, None)] * len(prefix),
                            (ResponseResult.UNKNOWN_ERROR, None),
                            (ResponseResult.OK, 2),
                            (ResponseResult.OK, MowerState.RESTRICTED),
                            (ResponseResult.OK, MowerActivity.PARKED),
                        ]
                    ),
                ) as read,
                patch(
                    "automower_ble.gardena.actions.asyncio.sleep",
                    new_callable=AsyncMock,
                ),
            ):
                assert await mower.mower_park_permanently() is ResponseResult.OK
                assert [c.args[0] for c in read.await_args_list] == [
                    *prefix,
                    "StartTrigger",
                    "GetMode",
                    "GetState",
                    "GetActivity",
                ]

    async def test_minimo_spot_sequence_still_delegates_to_original(self):
        mower = self.mower()
        for name in ("mower_spot_cut", "mower_stop_spot_cut"):
            with patch.object(
                Mower, name, AsyncMock(return_value=ResponseResult.OK)
            ) as original:
                assert await getattr(mower, name)() is ResponseResult.OK
                original.assert_awaited_once()

    async def test_park_does_not_hide_failure_or_unconfirmed_state(self):
        mower = self.mower()
        for fail_at in range(3):
            with patch.object(
                mower,
                "command_response",
                AsyncMock(
                    side_effect=[
                        *[(ResponseResult.OK, None)] * fail_at,
                        (ResponseResult.DEVICE_BUSY, None),
                    ]
                ),
            ) as read:
                assert (
                    await mower.mower_park_permanently() is ResponseResult.DEVICE_BUSY
                )
                assert read.await_count == fail_at + 1
        with (
            patch.object(
                mower,
                "command_response",
                AsyncMock(
                    side_effect=[
                        (ResponseResult.OK, None),
                        (ResponseResult.OK, None),
                        (ResponseResult.UNKNOWN_ERROR, None),
                        (ResponseResult.OK, 0),
                        (ResponseResult.OK, MowerState.IN_OPERATION),
                        (ResponseResult.OK, MowerActivity.MOWING),
                    ]
                ),
            ),
            patch(
                "automower_ble.gardena.actions.asyncio.sleep", new_callable=AsyncMock
            ),
        ):
            assert await mower.mower_park_permanently() is ResponseResult.UNKNOWN_ERROR

    async def test_g3_and_modern_spot_are_separate_and_gated(self):
        for kind, commands in (
            (
                14,
                [
                    "Pause",
                    "SetMode",
                    "SetOverrideMow",
                    "StartSpotCutting",
                    "StartTrigger",
                ],
            ),
            (
                43,
                [
                    "GetSpotCutAvailable",
                    "Pause",
                    "SetMode",
                    "PrepareSpotCutting",
                    "StartTrigger",
                ],
            ),
        ):
            mower = self.mower(kind)
            with patch.object(
                mower,
                "command_response",
                AsyncMock(return_value=(ResponseResult.OK, 1)),
            ) as read:
                assert await mower.mower_spot_cut() is ResponseResult.OK
                assert [c.args[0] for c in read.await_args_list] == commands
        with patch.object(
            self.mower(34),
            "command_response",
            AsyncMock(return_value=(ResponseResult.OK, 0)),
        ) as read:
            mower = self.mower(34)
            mower.command_response = read
            assert await mower.mower_spot_cut() is ResponseResult.NOT_AVAILABLE
            assert read.await_count == 1


def test_calendar_model_limits():
    task = TaskInformation(60, 30, True, False, False, False, False, False, False)
    with pytest.raises(ValueError, match="last schedule"):
        validate_tasks([], profile(14))
    with pytest.raises(ValueError, match="two schedules"):
        validate_tasks([task] * 3, profile(14))
    with pytest.raises(ValueError, match="at most"):
        validate_tasks([task] * 15, profile(14))
    validate_tasks([], profile(29))
    validate_tasks([task] * 15, profile(29))
