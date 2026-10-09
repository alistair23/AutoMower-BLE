"""Instance-local command selection for explicitly identified Gardena models."""

from automower_ble.protocol import ResponseResult


def corrected_protocol(protocol, capabilities=None):
    """Return model-selected definitions without modifying the input mapping."""
    result = dict(protocol)
    result["GetSpotCutAvailable"] = {"major": 4710, "minor": 0, "responseType": "bool"}
    result["AbortSpotCutting"] = {"major": 4710, "minor": 8}
    for label, major in (
        ("EcoMode", 4692),
        ("FrostSensor", 5370),
        ("FrostSensorLegacy", 5412),
    ):
        read, write = (6, 5) if label == "EcoMode" else (1, 2)
        suffix = "EnabledLegacy" if label.endswith("Legacy") else "Enabled"
        stem = label.removesuffix("Legacy")
        result[f"Get{stem}{suffix}"] = {
            "major": major,
            "minor": read,
            "responseType": "bool",
        }
        result[f"Set{stem}{suffix}"] = {
            "major": major,
            "minor": write,
            "requestType": {"enabled": "bool"},
        }
    # ObstacleAvoidance is radar; MobileLoop is ZoneProtect, not radar.
    result["GetAntiCollisionRadar"] = {
        "major": 5356,
        "minor": 7,
        "responseType": {
            "available": "bool",
            "enabled": "bool",
            "useAtBoundary": "bool",
        },
    }
    result["SetAntiCollisionRadarEnabled"] = {
        "major": 5356,
        "minor": 3,
        "requestType": {"enabled": "bool"},
    }
    result["GetZoneProtectSettings"] = {
        "major": 6050,
        "minor": 4,
        "responseType": {"enabled": "uint8", "available": "bool"},
    }
    result["SetZoneProtectEnabled"] = {
        "major": 6050,
        "minor": 3,
        "requestType": {"enabled": "bool"},
    }
    # Remove aliases that target unrelated settings or diagnostics.
    for name in (
        "GetChargingStationLoopSignalGeneration",
        "SetChargingStationLoopSignalGeneration",
        "GenerateLoopSignalLegacy",  # Actually disables obstacle avoidance.
        "GetSupportedAccessories",  # Actually front/rear collision status.
    ):
        result.pop(name, None)
    if capabilities is not None:
        if capabilities.generation == 4:
            result["GetCollisionSensorStatus"] = {
                "major": 4166,
                "minor": 8,
                "responseType": {"front": "bool", "rear": "bool"},
            }
            result["GetLiftSensorStatus"] = {
                "major": 4476,
                "minor": 6,
                "responseType": "bool",
            }
        if capabilities.generation in (3, 4):
            # App Calendar.AddTask is 8 time bytes + 7 weekday bools on both paths.
            result["AddTask"] = {
                "major": 4690,
                "minor": 7,
                "requestType": {
                    "start": "uint32",
                    "duration": "uint32",
                    **{
                        f"useOn{day}": "bool"
                        for day in (
                            "Monday",
                            "Tuesday",
                            "Wednesday",
                            "Thursday",
                            "Friday",
                            "Saturday",
                            "Sunday",
                        )
                    },
                },
            }
        for label, minor, response_type in (
            ("Enabled", 6, "bool"),
            ("Wire", 8, "uint8"),
            ("Distance", 10, "uint16"),
            ("Proportion", 12, "uint8"),
        ):
            result[f"GetStartingPoint{label}"] = {
                "major": 4706,
                "minor": minor,
                "requestType": {"startingPointId": "uint8"},
                "responseType": response_type,
            }
        if capabilities.zone_group is not None:
            for name in ("GetZoneProtectSettings", "SetZoneProtectEnabled"):
                result[name] = {**result[name], "major": capabilities.zone_group}
        if capabilities.corridor_read is not None:
            result["GetStartingPointCorridorCut"] = {
                "major": 4706,
                "minor": capabilities.corridor_read,
                "requestType": {"startingPointId": "uint8"},
                "responseType": "bool",
            }
            result["SetStartingPointCorridorCut"] = {
                "major": 4706,
                "minor": capabilities.corridor_read + 1,
                "requestType": {"startingPointId": "uint8", "corridorCut": "bool"},
            }
    return result


async def read_starting_point(mower, point_id):
    """Use G3 individual fields or G4 combined fields, with no write probing."""
    if mower.capabilities.generation != 3:
        return await mower.command_response(
            "GetStartingPoint", warn_on_error=False, startingPointId=point_id
        )
    point = {}
    for field in ("enabled", "proportion", "distance", "wire"):
        result, value = await mower.command_response(
            f"GetStartingPoint{field.title()}",
            warn_on_error=False,
            startingPointId=point_id,
        )
        if result is not ResponseResult.OK:
            return result, None
        if value is None or (field == "enabled" and setting_bool(value) is None):
            return ResponseResult.UNKNOWN_ERROR, None
        point[field] = value
    return ResponseResult.OK, point


async def set_starting_point_enabled(mower, point_id, enabled):
    """App G3/G4 workflow: disabling a point also clears its share."""
    mower.capabilities.validate_setting(
        "SetStartingPointEnabled", {"startingPointId": point_id, "enabled": enabled}
    )
    async with mower.lock:
        commands = [("SetStartingPointEnabled", {"enabled": enabled})]
        if not enabled:
            commands.append(("SetStartingPointProportion", {"proportion": 0}))
        commands.append(("SetStartingPointEnabled", {"enabled": enabled}))
        for name, values in commands:
            result, _ = await mower.command_response(
                name, startingPointId=point_id, **values
            )
            if result is not ResponseResult.OK:
                return result, None
        result, point = await read_starting_point(mower, point_id)
        if result is not ResponseResult.OK:
            return result, None
        if (
            not isinstance(point, dict)
            or setting_bool(point.get("enabled")) is not enabled
        ):
            return ResponseResult.UNKNOWN_ERROR, None
        if not enabled and point.get("proportion") != 0:
            return ResponseResult.UNKNOWN_ERROR, None
        return result, point


UNSUPPORTED = {
    ResponseResult.INVALID_GROUP,
    ResponseResult.INVALID_ID,
    ResponseResult.NOT_AVAILABLE,
}


def setting_bool(value):
    """Upstream decodes protocol bool as an integer byte; reject other data."""
    if type(value) in (bool, int) and value in (0, 1):
        return bool(value)
    return None


async def read_frost_setting(mower):
    """Select a supported module using reads only; never probe by writing."""
    suffixes = ("FrostSensor", "FrostSensorV1")
    capabilities = getattr(mower, "capabilities", None)
    if capabilities is not None:
        suffix = {5370: "FrostSensor", 5412: "FrostSensorV1"}.get(
            capabilities.frost_group
        )
        if suffix is None:
            return ResponseResult.NOT_AVAILABLE, None, None
        suffixes = (suffix,)
    for suffix in suffixes:
        result, value = await mower.command_response(
            (
                "GetFrostSensorEnabledLegacy"
                if suffix == "FrostSensorV1"
                else f"Get{suffix}Enabled"
            ),
            warn_on_error=False,
        )
        if result is ResponseResult.OK:
            enabled = setting_bool(value)
            if enabled is not None:
                return (
                    result,
                    enabled,
                    (
                        "SetFrostSensorEnabledLegacy"
                        if suffix == "FrostSensorV1"
                        else f"Set{suffix}Enabled"
                    ),
                )
            return ResponseResult.UNKNOWN_ERROR, None, None
        if result not in UNSUPPORTED:
            return result, None, None
    return result, None, None
