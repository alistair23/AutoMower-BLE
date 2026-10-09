# Opt-in Gardena profiles and connection lifecycle

## API boundary

The existing `automower_ble.mower.Mower` remains the generic client. It does not
automatically identify a Gardena profile or impose Gardena settings limits on
Husqvarna/unknown models. Shared connection and cancellation fixes apply to it.

`from automower_ble.gardena import GardenaMower` selects the audited Gardena app
profile explicitly. After `connect(device)` succeeds, call
`await mower.initialize_model(brand=...)`. This reads numeric model identity and
application firmware; it sends no setting, mode or start command. P14 guide rules
need explicit `brand="gardena"` or `brand="flymo"`; unspecified brand is not guessed.
An unknown profile refuses profile-specific actions/settings. Use the generic
client for devices outside this catalog. This API is additive and opt-in.

The following profile rules come from the retained GARDENA Bluetooth 9.2.0 app
audit, not manufacturer certification of every variant/firmware:

| Platform | Type identifiers | Points | SensorControl values | Point distance |
| --- | --- | --- | --- | --- |
| P0 / G3 | 14, 18, 22, 25 | 3 | 1, 2, 3 | 1–300 m |
| P005 / G4 | 29, 30 | 3 | 1, 2, 3 | 1–100 m |
| P005GA / G4 | 43 | 5 | 0, 1, 2, 3, 4 | 1–500 m |
| P14 / G4 | 34/{1,2,4}, 35/{1,2,3,7,8,9}, 36/1, 37/{1,2,3} | 5 | 0, 1, 2, 3, 4 | 1–500 m |

Unknown types/variants do not fall through to P14. P0 Frost uses 5412 through
20.28, then 5370; type 22 excludes it. P0 ZoneProtect uses 5926 and CorridorCut
24/25 from main firmware prefix 41, otherwise 6050 and 26/27. Missing/malformed
firmware disables those version-dependent writes rather than guessing.

## Settings and diagnostics

- `capabilities` exposes the immutable identified profile and its bounds.
- `get_settings()` reads drive/station distance, SensorControl, garage and radar
  fields when appropriate. `get_frost_setting()` returns result, enabled value
  and matching setter name. Other raw reads remain accessible through
  `command_response`; these methods are not a universal snapshot of all settings.
- `get_starting_point(id)` selects G3 individual fields or G4 combined reads.
- `set_setting(command, **values)` is the validated settings entry point. It
  checks model/ranges, exact argument names, booleans, and runtime radar/ZoneProtect
  availability. Frost writes require a valid matching-module read. Starting-point
  enable/disable follows the app's repeated writes, clears share on disable and
  verifies the result. Callers must inspect the returned ResponseResult.
- `get_diagnostics()` selects G3 Comboard/legacy loops or G4 diagnostics. Failed
  values remain unknown. Optional reads that return INVALID_GROUP, INVALID_ID or
  NOT_AVAILABLE, or raise KeyError, are remembered in the instance's
  `_unsupported_diagnostics` set by command name and arguments. Subsequent
  optional reads skip those entries until `initialize_model()` clears the set.
  Other failed replies are retried on later calls. This set is also used by
  optional settings and SpotCut-status reads; it does not store sensor values.
  No automatic polling is introduced. Raw orientation is in tenths of degrees, battery voltage
  in mV; UI conversion/history migration are the consumer's responsibility.
- `get_spot_status()` normalizes G3 versus G4 status without starting SpotCut.

Instance-local protocol selection separates radar (5356) from ZoneProtect
(6050/5926), corrects misleading aliases, selects model-specific starting-point
commands and uses the app's 15-byte AddTask layout for recognized generations.
It does not mutate the generic client's protocol or the global model catalog.
Raw `command`/`command_response` intentionally remain low-level APIs: they bypass
the guarded setting entry point and must not be presented as automatically safe.

## Actions and calendars

Permanent park follows G3 HOME/start or G4 HOME/clear/start. An UNKNOWN_ERROR
trigger reply is accepted only after successful fresh HOME/state/activity reads
confirm returning or parked/charging behavior. Explicit failures are not ignored.
Minimo SpotCut delegates to the existing tested upstream sequence; other reviewed
profiles use their app paths and availability gates. No movement occurs on setup.

Gardena calendars enforce G3/G4 limits (14/15), G3 two entries per day and refusal
to delete its last entry. Edits validate and verify read-back without changing
mode or overrides. Partial/uncertain writes block replacement until the app has
been checked and a fresh client is created. No rollback is inferred. The profile
calendar implementation is independent of the generic calendar safety PR #164,
so this PR is reviewable alone; the combined series is tested as well.

## Shared lifecycle changes

Connection setup, authentication, command transactions and cleanup share a
task-reentrant lock. Connected means the session is ready, not just that a BLE
link exists. Old keep-alive tasks are cancelled before reconnect; incomplete
sessions are cleaned up; disconnected writes raise BleakError; cancellation is
propagated instead of swallowed. No independent scanner/proxy selection policy,
HA configuration, duration defaults or mowing retries are introduced here.

## Evidence and remaining limits

Packet IDs, catalog and firmware rules are based on app constructor/control-flow
review; tests distinguish synthetic packets from hardware evidence. The owner
tested Minimo ECO/frost, SpotCut and start/park behavior in the downstream
integration. That is not physical certification of this new upstream client on
all models. The new facade is validated with fake transport and wire tests.

Physical other-model settings, parked calendars and loop completion remain open.
This PR does not claim to resolve City error 62 or unknown radio/proxy failures.
It excludes loop-event framing/completion (planned separately), HA entities,
blueprint growth/run-budget logic, app help text, recorder migration and SpotCut
UI restoration policy. No proprietary source, PINs or private captures are shipped.
