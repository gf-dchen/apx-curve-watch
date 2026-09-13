"""Console + log rendering of a ladder change, plus an optional Teams post.

Renders the NEW schedule for each changed resource, not a segment-by-segment
delta description -- the point is to see what's on file now, not to parse a diff.
"""

from __future__ import annotations

import logging
from datetime import date

from apx_curve_watch import teams
from apx_curve_watch.diff import ResourceDiff
from apx_curve_watch.snapshot import Ladders

logger = logging.getLogger("apx_curve_watch")


def _broadcast(message: str, teams_webhook_url: str | None) -> None:
    print(message)
    logger.warning(message.replace("\n", " | "))
    teams.post(teams_webhook_url, message)


def render(fordate: date, he: int, diffs: list[ResourceDiff], new_ladders: Ladders) -> str:
    lines = [f"[{fordate} HE{he:02d}] bid curve changed:"]
    for d in diffs:
        lines.append(f"  {d.resource}:")
        for mw, price in new_ladders.get(d.resource, []):
            lines.append(f"    {mw:>9.3f} MW @ {price:>10.4f}")
    return "\n".join(lines)


def announce(
    fordate: date,
    he: int,
    diffs: list[ResourceDiff],
    new_ladders: Ladders,
    *,
    teams_webhook_url: str | None = None,
) -> None:
    if not diffs:
        return
    _broadcast(render(fordate, he, diffs, new_ladders), teams_webhook_url)


def render_missing_bids(check_label: str, fordate: date, missing: tuple[str, ...]) -> str:
    return (
        f"[{check_label} CT check] no energy bids on file for {fordate} yet: {', '.join(missing)}"
    )


def announce_missing_bids(
    check_label: str,
    fordate: date,
    missing: tuple[str, ...],
    *,
    teams_webhook_url: str | None = None,
) -> None:
    if not missing:
        return
    _broadcast(render_missing_bids(check_label, fordate, missing), teams_webhook_url)
