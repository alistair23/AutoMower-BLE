# Read-only diagnostics

## Independent lifetime statistics

`await mower.mower_statistics()` returns six keys:

- `totalRunningTime`, `totalCuttingTime`, `totalChargingTime`,
  `totalSearchingTime`: raw seconds.
- `numberOfCollisions`, `numberOfChargingCycles`: counts.

Each uses its individual Statistics command (4726/1 through 4726/6). A rejected,
unavailable or malformed field is `None`; a valid zero remains zero. The method
does not require `GetAllStatistics`, does not read/reset the blade counter, and
does not introduce polling. Each call attempts all six counters again, including
those whose previous read failed. Exceptions raised by `command_response` are
not caught by this method. This PR does not change transport-level cancellation
handling; cancellation propagation is addressed separately in PR #165.
The six reads are not an atomic snapshot and support on every model is not implied.

The existing raw `GetAllStatistics` command remains available for consumers that
have independently established support for its complete layout.

## Collision and lift command names

`GetCollisionSensorStatus` is 4166/8 and returns two boolean fields, `front` and
`rear`. It replaces the misleading `GetSupportedAccessories` name and uint16
bitmask interpretation. Collision state is not accessory availability; callers
must not use either field to infer fitted accessories.

`GetLiftSensorStatus` is 4476/6 and returns a boolean. Both definitions describe
the modern diagnostic path; older mowers may instead need Comboard data. These
are raw command definitions, not instructions to query all models indiscriminately.
Model selection is intentionally outside this change. Read through
`command_response` and check the result before interpreting the value. The
existing decoder returns wire booleans as integer 0/1.

These layouts and individual-statistics reads were checked against the supplied
GARDENA Bluetooth 9.2.0 app command definitions/workflows. Tests include synthetic
packets with explicit IDs and payloads, not physical all-model certification.
This change does not diagnose or claim to fix the SILENO City error-62 report.
