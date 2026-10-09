"""Planner wall-clock timestamps must not invent an instant in a DST gap/fold."""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from automower_ble.timestamps import local_timestamp


@pytest.mark.parametrize(("month", "offset"), [(1, 1), (7, 2)])
def test_target_date_offset(month, offset):
    value = int(datetime(2026, month, 15, 10, tzinfo=UTC).timestamp())
    result = local_timestamp(value, ZoneInfo("Europe/Brussels"))
    assert result.hour == 10
    assert result.utcoffset() == timedelta(hours=offset)


@pytest.mark.parametrize(("month", "day"), [(3, 29), (10, 25)])
def test_gap_and_fold_are_unknown(month, day):
    value = int(datetime(2026, month, day, 2, 30, tzinfo=UTC).timestamp())
    assert local_timestamp(value, ZoneInfo("Europe/Brussels")) is None


@pytest.mark.parametrize("value", [None, 0, -1, 0xFFFFFFFF, True, 1.5, "123"])
def test_invalid_values(value):
    assert local_timestamp(value, UTC) is None


def test_fixed_offset_and_missing_timezone():
    assert local_timestamp(3600, UTC) == datetime(1970, 1, 1, 1, tzinfo=UTC)
    assert local_timestamp(3600, None) is None
