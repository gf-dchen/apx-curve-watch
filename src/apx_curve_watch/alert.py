"""Console + log rendering of a ladder change, plus an optional Teams post.

Renders the NEW schedule for each changed resource, not a segment-by-segment
delta description -- the point is to see what's on file now, not to parse a diff.

Teams gets the same text inside a ``CodeBlock`` element (see
``teams_codeblock``), not a bare ``TextBlock`` (wraps, and a multi-line one
collapses its own newlines) or a real ``Table`` element (columns squeeze
unreadably thin in Teams' narrow card pane) -- both confirmed live and ruled
out for exactly that reason.
"""

from __future__ import annotations

import logging
from datetime import date

from gfem.foundry.bidding import apx_bids

from apx_curve_watch import table, teams, teams_codeblock
from apx_curve_watch.diff import ResourceDiff
from apx_curve_watch.snapshot import Ladders

logger = logging.getLogger("apx_curve_watch")


def _broadcast(message: str, teams_webhook_url: str | None, *, title: str = "") -> None:
    print(message)
    logger.warning(message.replace("\n", " | "))
    if teams_webhook_url:
        card = teams_codeblock.build_card(message, title=title)
        teams.post_card(teams_webhook_url, card)


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
    bidset: apx_bids.BidSet | None = None,
    resources: tuple[str, ...] = (),
    teams_webhook_url: str | None = None,
) -> None:
    """Console/log get the concise per-resource change; Teams gets the full
    rest-of-day table instead (when ``bidset`` is given) -- though see
    ``teams_codeblock`` for the real ceiling on how much that can safely hold."""
    if not diffs:
        return
    console_message = render(fordate, he, diffs, new_ladders)
    print(console_message)
    logger.warning(console_message.replace("\n", " | "))
    if not teams_webhook_url:
        return
    if bidset is not None:
        teams_text = table.render_table(
            bidset,
            resources,
            hours=tuple(range(he, 25)),
            show_total=False,
            mw_decimals=0,
            price_prefix="$",
        )
        title = f"[{fordate} HE{he:02d}] bid curve changed -- rest of today"
    else:
        teams_text = console_message
        title = ""
    card = teams_codeblock.build_card(teams_text, title=title)
    teams.post_card(teams_webhook_url, card)


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
