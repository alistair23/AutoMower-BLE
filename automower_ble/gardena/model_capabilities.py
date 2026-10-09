"""Conservative, numeric model rules from the retained Gardena app audit.

Unknown devices do not inherit the app's context-dependent P14 default.
See docs/gardena-models.md for evidence and remaining limitations.
"""

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class ModelCapabilities:
    device_type: int | None = None
    variant: int | None = None
    platform: str = "unknown"
    generation: int | None = None
    firmware: str | None = None
    brand: str | None = None

    @property
    def schedule_limit(self):
        return {3: 14, 4: 15}.get(self.generation)

    @property
    def point_count(self):
        return {"P0": 3, "P005": 3, "P005GA": 5, "P14": 5}.get(self.platform, 0)

    @property
    def point_distance_bounds(self):
        maximum = {"P0": 300, "P005": 100, "P005GA": 500, "P14": 500}.get(self.platform)
        return (1, maximum) if maximum is not None else None

    @property
    def sensitivity_ids(self):
        if self.platform in ("P0", "P005"):
            return (1, 2, 3)
        if self.platform in ("P005GA", "P14"):
            return (0, 1, 2, 3, 4)
        return ()

    @property
    def wire_ids(self):
        if self.platform in ("P0", "P005"):
            return (2,)
        if self.platform == "P005GA":
            return (2, 3)
        if self.platform == "P14":
            if self.brand == "gardena":
                return (0, 1, 2, 3)
            if self.brand == "flymo":
                return (0, 1, 2)
        # App selects P14 guides using the application brand, not platform alone.
        return ()

    @property
    def drive_bounds(self):
        return {
            "P0": (20, 40),
            "P005": (20, 35),
            "P005GA": (20, 35),
            "P14": (25, 40),
        }.get(self.platform)

    @property
    def reversing_bounds(self):
        if self.platform == "P0":
            return (20, 300)
        if self.platform in ("P005", "P005GA", "P14"):
            return (60, 300)
        return None

    @property
    def firmware_pair(self):
        if not isinstance(self.firmware, str):
            return None
        match = re.fullmatch(r"(\d{2})\.(\d{2})(?:\.\d+)*", self.firmware.strip())
        return tuple(map(int, match.groups())) if match else None

    @property
    def frost_group(self):
        if self.device_type == 22:
            return None
        if self.platform == "P0":
            version = self.firmware_pair
            return None if version is None else (5370 if version > (20, 28) else 5412)
        return 5370 if self.platform in ("P005", "P005GA", "P14") else None

    @property
    def zone_group(self):
        if self.platform == "P0":
            version = self.firmware_pair
            return None if version is None else (5926 if version[0] >= 41 else 6050)
        return 6050 if self.platform in ("P005", "P005GA", "P14") else None

    @property
    def corridor_read(self):
        if self.platform == "P0":
            version = self.firmware_pair
            return None if version is None else (24 if version[0] >= 41 else 26)
        return 26 if self.platform in ("P005", "P005GA", "P14") else None

    @property
    def garage(self):
        return self.platform in ("P0", "P005", "P005GA")

    @property
    def radar(self):
        return self.platform == "P14"

    def validate_setting(self, command, values):
        """Enforce capability limits even for stale entities/service calls."""
        allowed = True
        if command == "SetSensorControlSensitivity":
            allowed = (
                type(values.get("sensitivity")) is int
                and values.get("sensitivity") in self.sensitivity_ids
            )
        elif command in ("SetDrivePastWire", "SetReversingDistance"):
            bounds = (
                self.drive_bounds
                if command == "SetDrivePastWire"
                else self.reversing_bounds
            )
            value = values.get("distance")
            allowed = (
                bounds is not None
                and type(value) is int
                and bounds[0] * 10 <= value <= bounds[1] * 10
            )
        elif command == "SetGarageEnabled":
            allowed = self.garage
        elif command == "SetAntiCollisionRadarEnabled":
            allowed = self.radar
        elif command == "SetZoneProtectEnabled":
            allowed = self.zone_group is not None
        elif command.startswith("SetFrostSensor"):
            allowed = command == {
                5370: "SetFrostSensorEnabled",
                5412: "SetFrostSensorEnabledLegacy",
            }.get(self.frost_group)
        elif command.startswith("SetStartingPoint"):
            point_id = values.get("startingPointId")
            allowed = type(point_id) is int and 1 <= point_id <= self.point_count
            if command == "SetStartingPointWire":
                allowed = (
                    allowed
                    and type(values.get("wire")) is int
                    and values.get("wire") in self.wire_ids
                )
            if command == "SetStartingPointDistance":
                bounds, distance = self.point_distance_bounds, values.get("distance")
                allowed = (
                    allowed
                    and bounds is not None
                    and type(distance) is int
                    and bounds[0] <= distance <= bounds[1]
                )
            if command == "SetStartingPointProportion":
                proportion = values.get("proportion")
                allowed = allowed and type(proportion) is int and 0 <= proportion <= 100
            if command == "SetStartingPointCorridorCut":
                allowed = allowed and self.corridor_read is not None
        if not allowed:
            raise ValueError(
                f"{command} is not confirmed for this model/firmware or value"
            )


def identify_model(identity, firmware=None, brand=None):
    if not isinstance(identity, dict):
        return ModelCapabilities()
    device_type, variant = identity.get("deviceType"), identity.get("deviceVariant")
    if type(device_type) is not int or type(variant) is not int:
        return ModelCapabilities()
    platform = {
        14: "P0",
        18: "P0",
        22: "P0",
        25: "P0",
        29: "P005",
        30: "P005",
        43: "P005GA",
    }.get(device_type, "unknown")
    # Explicit accepted type/variant pairs from app MowerModelKt.mowerModel.
    # Only these known catalog entries may reach the app's P14 default.
    p14_variants = {34: (1, 2, 4), 35: (1, 2, 3, 7, 8, 9), 36: (1,), 37: (1, 2, 3)}
    if variant in p14_variants.get(device_type, ()):
        platform = "P14"
    generation = 3 if platform == "P0" else (4 if platform != "unknown" else None)
    brand = brand if brand in ("gardena", "flymo") else None
    return ModelCapabilities(
        device_type, variant, platform, generation, firmware, brand
    )
