"""Explicit catalog/firmware matrix; separate capabilities from outbound layout."""

import unittest

import pytest

from automower_ble.gardena.model_capabilities import identify_model
from automower_ble.gardena.settings_protocol import corrected_protocol


CATALOG = {
    14: (1,),
    18: (1,),
    22: (1,),
    25: (1,),
    29: (1,),
    30: (1,),
    43: (1,),
    34: (1, 2, 4),
    35: (1, 2, 3, 7, 8, 9),
    36: (1,),
    37: (1, 2, 3),
}
FIRMWARE = (
    ("20.27", 5412, 6050, 26),
    ("20.28", 5412, 6050, 26),
    ("20.29", 5370, 6050, 26),
    ("40.99", 5370, 6050, 26),
    ("41.00", 5370, 5926, 24),
    ("41.01", 5370, 5926, 24),
    (None, None, None, None),
    ("41", None, None, None),
    ("41.xx", None, None, None),
    ("v41.00", None, None, None),
)


class MatrixTests(unittest.TestCase):
    def test_every_catalog_profile_at_each_firmware_boundary(self):
        for kind, variants in CATALOG.items():
            for variant in variants:
                for version, frost, zone, corridor in FIRMWARE:
                    for brand in (None, "gardena", "flymo"):
                        with self.subTest(
                            kind=kind, variant=variant, version=version, brand=brand
                        ):
                            c = identify_model(
                                {"deviceType": kind, "deviceVariant": variant},
                                version,
                                brand,
                            )
                            g3 = kind in (14, 18, 22, 25)
                            self.assertEqual(c.generation, 3 if g3 else 4)
                            self.assertEqual(c.schedule_limit, 14 if g3 else 15)
                            self.assertEqual(
                                c.point_count, 3 if g3 or kind in (29, 30) else 5
                            )
                            self.assertEqual(
                                c.frost_group,
                                None if kind == 22 else frost if g3 else 5370,
                            )
                            self.assertEqual(c.zone_group, zone if g3 else 6050)
                            self.assertEqual(c.corridor_read, corridor if g3 else 26)
                            self.assertEqual(c.radar, kind in (34, 35, 36, 37))

    def test_outbound_ranges_and_group_pairs_for_all_catalog_profiles(self):
        for kind, variants in CATALOG.items():
            for variant in variants:
                for version, _, _, _ in FIRMWARE:
                    c = identify_model(
                        {"deviceType": kind, "deviceVariant": variant},
                        version,
                        "gardena",
                    )
                    with self.subTest(kind=kind, variant=variant, version=version):
                        for command, bounds in (
                            ("SetDrivePastWire", c.drive_bounds),
                            ("SetReversingDistance", c.reversing_bounds),
                        ):
                            for value in (bounds[0] * 10, bounds[1] * 10):
                                c.validate_setting(command, {"distance": value})
                            for value in (bounds[0] * 10 - 1, bounds[1] * 10 + 1):
                                with pytest.raises(ValueError, match="not confirmed"):
                                    c.validate_setting(command, {"distance": value})
                        for value in range(5):
                            if value in c.sensitivity_ids:
                                c.validate_setting(
                                    "SetSensorControlSensitivity",
                                    {"sensitivity": value},
                                )
                            else:
                                with pytest.raises(ValueError, match="not confirmed"):
                                    c.validate_setting(
                                        "SetSensorControlSensitivity",
                                        {"sensitivity": value},
                                    )
                        overlay = corrected_protocol({}, c)
                        if c.zone_group is not None:
                            self.assertEqual(
                                overlay["GetZoneProtectSettings"]["major"], c.zone_group
                            )
                            self.assertEqual(
                                overlay["SetZoneProtectEnabled"]["major"], c.zone_group
                            )
                        if c.corridor_read is not None:
                            self.assertEqual(
                                overlay["GetStartingPointCorridorCut"]["minor"],
                                c.corridor_read,
                            )
                            self.assertEqual(
                                overlay["SetStartingPointCorridorCut"]["minor"],
                                c.corridor_read + 1,
                            )

    def test_unknown_pairs_and_malformed_identity_never_inherit_p14(self):
        for identity in (
            None,
            {},
            {"deviceType": True, "deviceVariant": 1},
            {"deviceType": 34, "deviceVariant": 3},
            {"deviceType": 35, "deviceVariant": 6},
            {"deviceType": 36, "deviceVariant": 2},
            {"deviceType": 37, "deviceVariant": 4},
            {"deviceType": 99, "deviceVariant": 1},
        ):
            c = identify_model(identity, "41.00", "gardena")
            self.assertEqual(c.platform, "unknown")
            self.assertFalse(c.radar)
            self.assertEqual(c.point_count, 0)
            with pytest.raises(ValueError, match="not confirmed"):
                c.validate_setting("SetAntiCollisionRadarEnabled", {"enabled": True})
