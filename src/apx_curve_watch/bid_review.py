"""Reasonability checks on a day-ahead book -- "does tomorrow's bid look wrong?".

Three desk rules, each a separate finding so one failure doesn't hide another:

1. **Charge block.** The overnight-into-morning fill has to actually be bid:
   across HE09-HE13 the book must carry at least 1000 MWh of charge, summed
   over the whole site (both ESRs, every hour in the block). A block that's
   simply light -- or one hour left empty -- shows up as a shortfall against
   that total.

2. **Discharge headroom.** In any hour that offers BOTH discharge energy and an
   AS product, the energy ladder must reach the resource's full 200 MW. Bidding
   only 150 MW there tells the optimizer the ESR tops out at 150, so it won't
   co-optimize 150 MW of energy against 50 MW of AS -- the capacity has to be
   visible on the energy curve for the stack to be reachable at all. Hours with
   no AS offered are exempt: a pure energy hour is free to offer less.

3. **Something to sell.** The day has to bid discharge *somewhere*. A book that
   only charges passes every other rule -- rule 2 tests hours that discharge, and
   a book with no discharge at all simply has none to test -- so a half-built
   book sails through without this.

4. **ESR symmetry.** The two ESRs are bid as one site and normally mirror each
   other exactly, so an hour where their ladders differ is nearly always a
   half-applied edit rather than an intended split.

Energy ladders come from ``curve_points``, not ``apx_bids.ladder``, for the
shared-price reason that module documents. MW keeps the repo-wide sign
convention: negative is charge, positive discharge.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from apx_curve_watch.curve_points import curve_points
from apx_curve_watch.day_book import DayBook

ALL_HOURS = tuple(range(1, 25))


@dataclass(frozen=True)
class Finding:
    """One failed rule: a one-line headline plus the rows that justify it."""

    kind: str  # "charge-block" | "discharge-headroom" | "esr-mismatch"
    headline: str
    lines: list[str]


def _points(book: DayBook, resource: str, he: int) -> list[tuple[float, float]]:
    return curve_points(book.bidset, he, resource) if book.bidset else []


def charge_mw(book: DayBook, resource: str, he: int) -> float:
    """MW of charge bid for one resource-hour, as a positive magnitude (0 if none)."""
    return -min((mw for mw, _ in _points(book, resource, he) if mw < 0), default=0.0)


def discharge_mw(book: DayBook, resource: str, he: int) -> float:
    """Top of the discharge ladder for one resource-hour (0 if it doesn't sell)."""
    return max((mw for mw, _ in _points(book, resource, he) if mw > 0), default=0.0)


def review_resources(book: DayBook, resources: tuple[str, ...]) -> tuple[str, ...]:
    """Which resources to review: the configured set, else whatever the book holds."""
    if resources:
        return resources
    return tuple(book.bidset.resources) if book.bidset else ()


def check_charge_block(
    book: DayBook, resources: tuple[str, ...], hours: tuple[int, ...], target_mwh: float
) -> Finding | None:
    """Rule 1 -- site-wide charge across the block, against ``target_mwh``."""
    if not hours:
        return None
    by_hour = {he: sum(charge_mw(book, r, he) for r in resources) for he in hours}
    total = sum(by_hour.values())
    if total >= target_mwh:
        return None
    return Finding(
        kind="charge-block",
        headline=(
            f"charge HE{min(hours):02d}-HE{max(hours):02d}: {total:,.0f} MWh site-wide, "
            f"{target_mwh - total:,.0f} short of {target_mwh:,.0f}"
        ),
        # Charge shown signed, the way it sits on the curve -- but an hour with
        # nothing bid is a plain "0", never the "-0" that negating zero gives.
        lines=[
            "  ".join(
                f"HE{he:02d} {-by_hour[he]:,.0f}" if by_hour[he] else f"HE{he:02d} 0"
                for he in hours
            )
        ],
    )


def check_discharge_headroom(
    book: DayBook, resources: tuple[str, ...], min_mw: float
) -> Finding | None:
    """Rule 2 -- full-capacity energy ladder wherever energy and AS are both bid."""
    lines = []
    for resource in resources:
        for he in ALL_HOURS:
            top = discharge_mw(book, resource, he)
            if top <= 0 or book.as_mw(resource, he) <= 0 or top >= min_mw:
                continue
            products = ", ".join(
                f"{p} {mw:,.0f}" for p, mw in sorted(book.as_products(resource, he).items())
            )
            lines.append(f"{resource} HE{he:02d}: tops out at {top:,.0f} MW, with {products}")
    if not lines:
        return None
    return Finding(
        kind="discharge-headroom",
        headline=f"discharge ladder under {min_mw:,.0f} MW in an hour that also bids AS:",
        lines=lines,
    )


def check_day_sells(book: DayBook, resources: tuple[str, ...]) -> Finding | None:
    """Rule 3 -- the day sells at some point.

    Deliberately a bare presence check, not a target: how much to sell and when
    is the trade, but a day that never sells at all is a book someone stopped
    building halfway.
    """
    if any(discharge_mw(book, r, he) > 0 for r in resources for he in ALL_HOURS):
        return None
    charged = sum(charge_mw(book, r, he) for r in resources for he in ALL_HOURS)
    return Finding(
        kind="no-discharge",
        headline="no discharge bid in any hour of the day",
        lines=[f"{charged:,.0f} MWh of charge bid site-wide, nothing to sell it back into"],
    )


def _ladder_text(points: list[tuple[float, float]]) -> str:
    return ", ".join(f"{mw:,.0f}@${price:,.2f}" for mw, price in points) or "(nothing)"


def check_esr_symmetry(book: DayBook, resources: tuple[str, ...]) -> Finding | None:
    """Rule 4 -- every reviewed resource's energy ladder identical, hour by hour."""
    if len(resources) < 2:
        return None
    lines = []
    for he in ALL_HOURS:
        ladders = {r: _points(book, r, he) for r in resources}
        if len({tuple(pts) for pts in ladders.values()}) < 2:
            continue
        lines.append(f"HE{he:02d}:")
        lines.extend(f"  {r}: {_ladder_text(pts)}" for r, pts in ladders.items())
    if not lines:
        return None
    return Finding(
        kind="esr-mismatch",
        headline="ESRs are bid differently (they normally mirror):",
        lines=lines,
    )


def review(
    book: DayBook,
    resources: tuple[str, ...],
    *,
    charge_block_hours: tuple[int, ...],
    charge_block_mwh: float,
    min_discharge_mw: float,
    check_discharge_present: bool,
    check_symmetry: bool,
) -> list[Finding]:
    """Every rule that fails on ``book``; empty when the book looks right."""
    names = review_resources(book, resources)
    if not names:
        return []
    candidates = [
        check_charge_block(book, names, charge_block_hours, charge_block_mwh),
        check_day_sells(book, names) if check_discharge_present else None,
        check_discharge_headroom(book, names, min_discharge_mw),
        check_esr_symmetry(book, names) if check_symmetry else None,
    ]
    return [f for f in candidates if f is not None]


def render_review(findings: list[Finding]) -> str:
    """The findings as an indented block -- the body of the warning, no header."""
    lines: list[str] = []
    for finding in findings:
        lines.append(finding.headline)
        lines.extend(f"  {line}" for line in finding.lines)
    return "\n".join(lines)


def review_header(check_label: str, fordate: date, findings: list[Finding]) -> str:
    """The warning's one-line header. ``check_label`` is the scheduled check's
    wall clock (``"08:30"``); empty for a run that isn't on the schedule."""
    count = len(findings)
    prefix = f"[{check_label} CT check] " if check_label else ""
    return (
        f"{prefix}{fordate} day-ahead bid looks wrong "
        f"({count} check{'' if count == 1 else 's'} failed)"
    )
