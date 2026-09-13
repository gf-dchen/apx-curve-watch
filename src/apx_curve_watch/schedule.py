"""Parse a comma-separated list of wall-clock times, e.g. ``"08:00,08:15"``."""

from __future__ import annotations

from datetime import time


def parse_check_times(raw: str) -> tuple[time, ...]:
    times: list[time] = []
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        hour, minute = chunk.split(":")
        times.append(time(int(hour), int(minute)))
    return tuple(sorted(set(times)))
