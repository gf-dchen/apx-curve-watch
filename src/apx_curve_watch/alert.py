"""Console + log rendering of a ladder change, plus an optional Teams post."""

from __future__ import annotations

import logging
from datetime import date

from apx_curve_watch import teams
from apx_curve_watch.diff import Point, ResourceDiff

logger = logging.getLogger("apx_curve_watch")


def _fmt_point(p: Point) -> str:
    if p is None:
        return "-"
    mw, price = p
    return f"{mw:>9.3f} MW @ {price:>10.4f}"


def render(fordate: date, he: int, diffs: list[ResourceDiff]) -> str:
    lines = [f"[{fordate} HE{he:02d}] bid curve changed:"]
    for d in diffs:
        lines.append(f"  {d.resource}:")
        for seg in d.segments:
            lines.append(
                f"    seg {seg.index + 1:>2} {seg.kind:<7} "
                f"{_fmt_point(seg.before)} -> {_fmt_point(seg.after)}"
            )
    return "\n".join(lines)


def announce(
    fordate: date, he: int, diffs: list[ResourceDiff], *, teams_webhook_url: str | None = None
) -> None:
    if not diffs:
        return
    message = render(fordate, he, diffs)
    print(message)
    logger.warning("curve change: %s", message.replace("\n", " | "))
    teams.post(teams_webhook_url, message)
