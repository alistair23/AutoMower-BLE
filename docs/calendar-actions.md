# Calendar and action safety

## Calendar replacement

`get_tasks()` now raises on an unavailable, partial or malformed calendar rather
than returning an empty list. An empty list means a successful zero-count read.
The one-based ID fallback is attempted only if task zero explicitly returns
INVALID_ID, not after transient or partial failures. Non-minute times are rejected
instead of silently rounding them and changing a later replacement.

`set_tasks(tasks, expected=previous_tasks)` optionally checks that the calendar
still matches the caller's earlier snapshot. Omit `expected` for an intentional
replacement of the current calendar. It validates inputs before writes and holds
the existing command lock across preflight, transaction and read-back. Reads and
other commands cannot interleave on the same client. Other BLE clients are not
covered by this lock. Ordering differences are ignored; duplicate entries are not.

Calendar edits no longer call resume-schedule, change operating mode, clear a
mowing/parking override or send StartTrigger. A caller that intends to resume
operation must request that separately. This deliberately removes the previous
automatic transition out of permanent parking after a nonempty replacement.

A rejected/interrupted transaction or failed/mismatched read-back leaves the
client's replacement path blocked, including `clear_tasks()`. There is no blind
retry, rollback or commit after a failure. Read-only inspection remains possible.
Verify the actual calendar in the manufacturer app before creating a new Mower
instance to try another replacement. Disconnect/reconnect alone does not clear
the guard. The library cannot guarantee firmware transaction rollback.

This PR retains the existing generic 15-task ceiling and AddTask wire definition,
including its existing trailing field. Model-specific capacity/last-task rules
and model-selected wire layouts belong in the subsequent capability PR. It does
not claim to make all calendar operations valid on every mower model.

## Action replies

`mower_pause()` and `mower_resume()` now return ResponseResult. Callers should
check it; existing callers that ignore the return continue to work. Resume sends
one StartTrigger, with no retry. Only UNKNOWN_ERROR can be reconciled using the
existing delayed read-back mechanism: both reads must succeed and show
IN_OPERATION with GOING_OUT, MOWING or GOING_HOME. An OK reply succeeds directly;
other non-OK replies remain failures.

The existing manual-mow/SpotCut read-back helper also now checks both read result
codes. Their command sequences are unchanged, as is permanent park in this PR.
An operation's success cannot be inferred from stale or rejected read payloads.
This change does not diagnose earlier reports involving overlapping commands.

## Next start and timezone

Pass an IANA/rule-based tzinfo such as ZoneInfo("Europe/Brussels") to
`mower_next_start_time()` to apply the target date's seasonal offset. Zero,
0xFFFFFFFF and malformed timestamps, DST gaps and ambiguous folds return None.
The existing omitted-timezone fallback is retained for compatibility, but a
fixed offset cannot describe future seasonal changes. No production/message
clock assumptions or HA display formatting are changed here.

Tests use fake responses and synthetic calendars, not physical parked-calendar
certification. No mower commands were sent while preparing this patch.
