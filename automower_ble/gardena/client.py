"""Explicit Gardena client with read-only identification and guarded settings."""

from automower_ble.mower import Mower
from automower_ble.protocol import ResponseResult

from .actions import ActionMixin
from .model_capabilities import ModelCapabilities, identify_model
from .model_diagnostics import (
    read_model_diagnostics,
    read_model_settings,
    read_spot_status,
)
from .schedule import ScheduleMixin
from .settings_protocol import (
    corrected_protocol,
    read_frost_setting,
    read_starting_point,
    set_starting_point_enabled,
    setting_bool,
)


class GardenaMower(ActionMixin, ScheduleMixin, Mower):
    """Use only after choosing the Gardena app-profile API explicitly.

    connect() does not identify or change settings automatically. Call
    initialize_model() after connecting. Unknown profiles refuse profile-specific
    actions; use the original Mower for devices outside the audited catalog.
    Raw command/command_response remain low-level escape hatches; set_setting
    is the validated settings interface, not a transport-level access control.
    """

    def __init__(self, channel_id: int, address, pin=None):
        super().__init__(channel_id, address, pin)
        self.capabilities = ModelCapabilities()
        self._base_protocol = None
        self._unsupported_diagnostics: set[
            tuple[str, tuple[tuple[str, object], ...]]
        ] = set()

    async def initialize_model(self, brand=None):
        """Identify using reads only; require explicit P14 brand context."""
        async with self.lock:
            identity_result, identity = await self.command_response(
                "GetModel", warn_on_error=False
            )
            firmware_result, firmware = await self.command_response(
                "GetSwVersionStringAppl", warn_on_error=False
            )
            self.capabilities = identify_model(
                identity if identity_result is ResponseResult.OK else None,
                firmware if firmware_result is ResponseResult.OK else None,
                brand,
            )
            self._unsupported_diagnostics.clear()
            return self.capabilities

    async def get_protocol(self):
        if self._base_protocol is None:
            self._base_protocol = dict(await super().get_protocol())
        return corrected_protocol(self._base_protocol, self.capabilities)

    async def get_diagnostics(self):
        """Return model-selected raw diagnostics; no writes or UI policy."""
        async with self.lock:
            return await read_model_diagnostics(self, self._unsupported_diagnostics)

    async def get_settings(self):
        async with self.lock:
            return await read_model_settings(self, self._unsupported_diagnostics)

    async def get_spot_status(self):
        return await read_spot_status(self, self._unsupported_diagnostics)

    async def get_frost_setting(self):
        """Return (result, enabled, matching setter) without probing writes."""
        async with self.lock:
            return await read_frost_setting(self)

    async def get_starting_point(self, point_id):
        if (
            type(point_id) is not int
            or not 1 <= point_id <= self.capabilities.point_count
        ):
            raise ValueError("Starting point is not confirmed for this model")
        async with self.lock:
            return await read_starting_point(self, point_id)

    async def set_setting(self, command, **values):
        """Validate model/range and runtime availability before a setting write."""
        allowed = {
            "SetEcoModeEnabled",
            "SetSensorControlEnabled",
            "SetSensorControlSensitivity",
            "SetDrivePastWire",
            "SetReversingDistance",
            "SetGarageEnabled",
            "SetAntiCollisionRadarEnabled",
            "SetZoneProtectEnabled",
            "SetFrostSensorEnabled",
            "SetFrostSensorEnabledLegacy",
            "SetStartingPointEnabled",
            "SetStartingPointWire",
            "SetStartingPointDistance",
            "SetStartingPointProportion",
            "SetStartingPointCorridorCut",
        }
        async with self.lock:
            if command not in allowed or self.capabilities.generation is None:
                raise ValueError("Setting is not confirmed for this model")
            self.capabilities.validate_setting(command, values)
            definition = (await self.get_protocol())[command]
            fields = definition.get("requestType", {})
            if set(values) != set(fields):
                raise ValueError("Setting parameters do not match the command")
            for key, kind in fields.items():
                if kind == "bool" and type(values[key]) is not bool:
                    raise ValueError("Boolean setting requires True or False")
            if command.startswith("SetFrostSensor"):
                status, _, setter = await read_frost_setting(self)
                if status is not ResponseResult.OK:
                    return status
                if setter != command:
                    return ResponseResult.NOT_AVAILABLE
            if command in ("SetAntiCollisionRadarEnabled", "SetZoneProtectEnabled"):
                read_command = (
                    "GetAntiCollisionRadar"
                    if command == "SetAntiCollisionRadarEnabled"
                    else "GetZoneProtectSettings"
                )
                status, data = await self.command_response(
                    read_command, warn_on_error=False
                )
                if status is not ResponseResult.OK:
                    return status
                if (
                    not isinstance(data, dict)
                    or setting_bool(data.get("available")) is not True
                ):
                    return ResponseResult.NOT_AVAILABLE
            if command == "SetStartingPointEnabled":
                status, _ = await set_starting_point_enabled(
                    self, values["startingPointId"], values["enabled"]
                )
                return status
            result, _ = await self.command_response(command, **values)
            return result
