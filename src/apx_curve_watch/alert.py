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

from apx_curve_watch import bid_review, table, teams, teams_codeblock
from apx_curve_watch.bid_review import Finding
from apx_curve_watch.diff import HourChange

logger = logging.getLogger("apx_curve_watch")


def _broadcast(
    message: str,
    teams_webhook_url: str | None,
    *,
    title: str = "",
    teams_text: str | None = None,
) -> None:
    """Console + log get ``message``; Teams gets ``teams_text`` under ``title``
    when the caller wants the header as a card title rather than repeated inside
    the code block."""
    print(message)
    logger.warning(message.replace("\n", " | "))
    if teams_webhook_url:
        card = teams_codeblock.build_card(
            teams_text if teams_text is not None else message, title=title
        )
        teams.post_card(teams_webhook_url, card)


def hours_text(changes: list[HourChange]) -> str:
    return ", ".join(f"HE{c.he:02d}" for c in changes)


def render(fordate: date, changes: list[HourChange]) -> str:
    lines = [f"[{fordate}] bid curve changed -- {hours_text(changes)}:"]
    for change in changes:
        for d in change.diffs:
            lines.append(f"  HE{change.he:02d} {d.resource}:")
            for mw, price in change.ladders.get(d.resource, []):
                lines.append(f"    {mw:>9.3f} MW @ {price:>10.4f}")
    return "\n".join(lines)


def announce(
    fordate: date,
    changes: list[HourChange],
    *,
    bidset: apx_bids.BidSet | None = None,
    resources: tuple[str, ...] = (),
    current_he: int | None = None,
    teams_webhook_url: str | None = None,
) -> None:
    """Console/log get the concise per-hour change; Teams gets the day table
    instead (when ``bidset`` is given) -- though see ``teams_codeblock`` for the
    real ceiling on how much that can safely hold.

    The table starts at the earliest hour that moved, or at ``current_he`` when
    that is earlier still, so a change to a later hour is read in the context of
    the day that is actually left to trade."""
    if not changes:
        return
    console_message = render(fordate, changes)
    print(console_message)
    logger.warning(console_message.replace("\n", " | "))
    if not teams_webhook_url:
        return
    title = f"[{fordate}] bid curve changed -- {hours_text(changes)}"
    if bidset is not None:
        start = min([c.he for c in changes] + ([current_he] if current_he else []))
        teams_text = table.render_table(
            bidset,
            resources,
            hours=tuple(range(start, 25)),
            show_total=False,
            mw_decimals=0,
            price_prefix="$",
        )
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


def announce_bid_review(
    check_label: str,
    fordate: date,
    findings: list[Finding],
    *,
    teams_webhook_url: str | None = None,
) -> None:
    """Announce a day-ahead book that fails one or more reasonability rules.

    Silent when ``findings`` is empty -- a book that looks right is not news,
    same as the missing-bids nudge it runs alongside."""
    if not findings:
        return
    header = bid_review.review_header(check_label, fordate, findings)
    body = bid_review.render_review(findings)
    _broadcast(f"{header}\n{body}", teams_webhook_url, title=header, teams_text=body)
