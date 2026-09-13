"""Parse a comma-separated schedule spec into the set of wall-clock times to check.

Each entry is either a single time (``"08:00"``, fires once) or a window with a
cadence (``"08:30-09:00:15"``, fires every 15 minutes from 08:30 through 09:00
inclusive) -- so checking rarely far from a deadline and often right up against
it are both expressible in one list, e.g.
``"08:30-09:00:15,09:00-09:30:10,09:30-10:00:5"``.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta

_WINDOW_ANCHOR = datetime(2000, 1, 1)


def _parse_time(raw: str) -> time:
    hour, minute = raw.strip().split(":")
    return time(int(hour), int(minute))


def _expand_window(start: time, end: time, interval_minutes: int) -> list[time]:
    current = datetime.combine(_WINDOW_ANCHOR, start)
    stop = datetime.combine(_WINDOW_ANCHOR, end)
    step = timedelta(minutes=interval_minutes)
    times: list[time] = []
    while current <= stop:
        times.append(current.time())
        current += step
    return times


def parse_check_times(raw: str) -> tuple[time, ...]:
    times: list[time] = []
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "-" in chunk:
            span, _, interval_raw = chunk.rpartition(":")
            start_raw, end_raw = span.split("-")
            times.extend(
                _expand_window(_parse_time(start_raw), _parse_time(end_raw), int(interval_raw))
            )
        else:
            times.append(_parse_time(chunk))
    return tuple(sorted(set(times)))
