"""Decode device-local planner times without guessing across DST transitions."""

from datetime import UTC, datetime, tzinfo


def local_timestamp(value: int | None, timezone: tzinfo | None) -> datetime | None:
    """Return the unique valid instant, or None for sentinels, DST gaps or folds.

    Supply a rule-based timezone (for example ZoneInfo) for future-date DST.
    A fixed offset cannot describe seasonal changes.
    """
    if type(value) is not int or not 0 < value < 0xFFFFFFFF or timezone is None:
        return None
    try:
        wall = datetime.fromtimestamp(value, UTC).replace(tzinfo=None)
        candidates = {}
        for fold in (0, 1):
            candidate = wall.replace(tzinfo=timezone, fold=fold)
            utc = candidate.astimezone(UTC)
            if utc.astimezone(timezone).replace(tzinfo=None) == wall:
                candidates[utc] = candidate
        return next(iter(candidates.values())) if len(candidates) == 1 else None
    except (ValueError, OverflowError, OSError):
        return None
