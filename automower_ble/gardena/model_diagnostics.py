"""Generation-selected diagnostics with retryable failures kept unknown."""

from automower_ble.protocol import ResponseResult
from .settings_protocol import UNSUPPORTED, setting_bool


async def read_optional(mower, unsupported, command, **kwargs):
    key = (command, tuple(sorted(kwargs.items())))
    if key in unsupported:
        return None
    try:
        result, value = await mower.command_response(
            command, warn_on_error=False, **kwargs
        )
    except KeyError:
        unsupported.add(key)
        return None
    except (ValueError, IndexError):
        return None
    if result in UNSUPPORTED:
        unsupported.add(key)
    return value if result is ResponseResult.OK else None


async def read_model_diagnostics(mower, unsupported):
    caps = mower.capabilities
    data = {}

    async def read(name, **kwargs):
        return await read_optional(mower, unsupported, name, **kwargs)

    if caps.generation == 3:
        for command, keys in (
            (
                "GetComboardSensorData",
                (
                    "collision",
                    "lift",
                    "upsideDown",
                    "pitch",
                    "roll",
                    "mowerTemperature",
                ),
            ),
            (
                "GetSignalQuality",
                (
                    "signalQuality",
                    "a0Signal",
                    "fSignal",
                    "nSignal",
                    "guide1Signal",
                    "messageFromChargingStation",
                    "inChargingStation",
                ),
            ),
        ):
            values = await read(command)
            for key in keys:
                value = values.get(key) if isinstance(values, dict) else None
                data[key] = (
                    setting_bool(value)
                    if key in ("collision", "lift", "upsideDown", "inChargingStation")
                    else value
                )
    elif caps.generation == 4:
        for key, command in (
            ("batteryVoltage", "GetBatteryVoltage"),
            ("batteryCurrent", "GetBatteryCurrent"),
            ("batteryTemperature", "GetBatteryTemperature"),
            ("orientationPitch", "GetOrientationPitch"),
            ("orientationRoll", "GetOrientationRoll"),
        ):
            value = await read(command)
            data[key] = (
                value if type(value) in (int, float) and value != 999999 else None
            )
        collision = await read("GetCollisionSensorStatus")
        front = (
            setting_bool(collision.get("front"))
            if isinstance(collision, dict)
            else None
        )
        rear = (
            setting_bool(collision.get("rear")) if isinstance(collision, dict) else None
        )
        data["collision"] = (
            (front or rear) if front is not None and rear is not None else None
        )
        data["lift"] = setting_bool(await read("GetLiftSensorStatus"))
        front = await read("GetLoopSignalStrength", signalType=0)
        rear = await read("GetLoopSignalStrength", signalType=1)
        data["loopSignalStrength"] = (
            (front + rear) / 2
            if type(front) in (int, float) and type(rear) in (int, float)
            else None
        )
        signals = await read("GetLoopSignals", signalType=0)
        keys = ["a0Signal", "fSignal", "nSignal", "guide1Signal"]
        if 3 in caps.wire_ids:
            keys.append("guide2Signal")
        for key in keys:
            data[key] = signals.get(key) if isinstance(signals, dict) else None
    return data


async def read_spot_status(mower, unsupported):
    generation = mower.capabilities.generation
    if generation not in (3, 4):
        return None
    if mower.capabilities.platform in ("P14", "P005GA"):
        available = await read_optional(mower, unsupported, "GetSpotCutAvailable")
        if setting_bool(available) is not True:
            return None
    command = "GetSpotCutting" if generation == 3 else "GetSpotCuttingState"
    value = await read_optional(mower, unsupported, command)
    if generation == 3:
        # G3 IDLE/ACTIVE is not G4 NOT_ACTIVE/IDLE/PENDING_START/RUNNING.
        value = setting_bool(value)
        return None if value is None else (3 if value else 0)
    return value if type(value) is int and value in (0, 1, 2, 3) else None


async def read_model_settings(mower, unsupported):
    """Read settings independently; busy replies must not disable a whole family."""
    caps = mower.capabilities
    data = {}
    for key, command, supported in (
        ("DrivePastWire", "GetDrivePastWire", caps.drive_bounds is not None),
        (
            "ReversingDistance",
            "GetReversingDistance",
            caps.reversing_bounds is not None,
        ),
        (
            "SensorControlSensitivity",
            "GetSensorControlSensitivity",
            bool(caps.sensitivity_ids),
        ),
        ("SensorControlEnabled", "GetSensorControlEnabled", bool(caps.sensitivity_ids)),
    ):
        value = await read_optional(mower, unsupported, command) if supported else None
        data[key] = setting_bool(value) if key == "SensorControlEnabled" else value
    garage = (
        await read_optional(mower, unsupported, "GetGarageEnabled")
        if caps.garage
        else None
    )
    data["GarageEnabled"] = setting_bool(garage)
    data["garageSupported"] = True if data["GarageEnabled"] is not None else None
    radar = (
        await read_optional(mower, unsupported, "GetAntiCollisionRadar")
        if caps.radar
        else None
    )
    radar = radar if isinstance(radar, dict) else {}
    data["AntiCollisionRadarAvailable"] = setting_bool(radar.get("available"))
    data["antiCollisionRadarSupported"] = data["AntiCollisionRadarAvailable"]
    data["AntiCollisionRadarEnabled"] = (
        setting_bool(radar.get("enabled"))
        if data["AntiCollisionRadarAvailable"] is True
        else None
    )
    return data
