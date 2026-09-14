"""Render today's full-day energy ladder, HE by HE, as a plain-text table -- the
same HE01..HE24 layout as the APX MarketSuite bid-curve page.

Energy only: AS-Market products (ECRS etc., visible on the APX page but not
extracted by ``gfem``'s parser) are out of scope here -- see the handoff. Rows
are "Point N - MW" / "Point N - $" pairs, one pair per curve segment, resolved
via ``curve_points`` (not ``apx_bids.ladder`` directly -- see that module for
why a curve's own points can otherwise go missing).
"""

from __future__ import annotations

from gfem.foundry.bidding import apx_bids

from apx_curve_watch.curve_points import curve_points

ALL_HOURS = tuple(range(1, 25))
_LABEL_WIDTH = 14
_COL_WIDTH = 9


def resource_rows(bidset: apx_bids.BidSet, resource: str) -> list[tuple[str, dict[int, float]]]:
    """``[(row_label, {he: value})]`` for one resource's energy ladder across the day."""
    ladders = {he: curve_points(bidset, he, resource) for he in ALL_HOURS}
    max_points = max((len(pts) for pts in ladders.values()), default=0)

    rows: list[tuple[str, dict[int, float]]] = []
    for i in range(max_points):
        mw_row = {he: pts[i][0] for he, pts in ladders.items() if i < len(pts)}
        price_row = {he: pts[i][1] for he, pts in ladders.items() if i < len(pts)}
        rows.append((f"Point {i + 1} - MW", mw_row))
        rows.append((f"Point {i + 1} - $", price_row))
    return rows


def _fmt(value: float | None, *, decimals: int = 2, prefix: str = "") -> str:
    if value is None:
        return " " * _COL_WIDTH
    return f"{prefix}{value:.{decimals}f}".rjust(_COL_WIDTH)


def _has_any_point(bidset: apx_bids.BidSet, resource: str, he: int) -> bool:
    return bool(curve_points(bidset, he, resource))


def _resource_has_any_data(bidset: apx_bids.BidSet, resource: str, hours: tuple[int, ...]) -> bool:
    return any(_has_any_point(bidset, resource, he) for he in hours)


def _column_plan(
    bidset: apx_bids.BidSet, resources: tuple[str, ...], hours: tuple[int, ...]
) -> list[int | None]:
    """One entry per column to render: an hour, or ``None`` for one collapsed
    ``...`` placeholder standing in for a run of consecutive hours where NONE
    of ``resources`` has anything on file -- a run of individually-blank
    columns just wastes width."""
    plan: list[int | None] = []
    in_gap = False
    for he in hours:
        if any(_has_any_point(bidset, r, he) for r in resources):
            plan.append(he)
            in_gap = False
        elif not in_gap:
            plan.append(None)
            in_gap = True
    return plan


def render_table(
    bidset: apx_bids.BidSet,
    resources: tuple[str, ...] = (),
    hours: tuple[int, ...] = ALL_HOURS,
    *,
    show_total: bool = True,
    mw_decimals: int = 2,
    price_decimals: int = 2,
    price_prefix: str = "",
) -> str:
    """``hours`` narrows which HE columns are shown (and what Total sums over) --
    e.g. ``tuple(range(current_he, 25))`` for "the rest of today". A resource
    with nothing on file anywhere in ``hours`` is left out entirely rather than
    printed as an all-blank section.

    ``show_total``/``mw_decimals``/``price_decimals``/``price_prefix`` all
    default to match the APX page (Total column, 2dp, no prefix); a caller
    wanting a more compact rendering (e.g. for Teams) overrides them."""
    names = [r for r in (resources or bidset.resources) if _resource_has_any_data(bidset, r, hours)]
    plan = _column_plan(bidset, names, hours)

    def _label(col: int | None) -> str:
        return "..." if col is None else f"HE{col:02d}"

    header = "".join(_label(col).rjust(_COL_WIDTH) for col in plan)
    if show_total:
        header += "Total".rjust(_COL_WIDTH)
    lines = [" " * _LABEL_WIDTH + header]
    for resource in names:
        lines.append(resource)
        for label, values in resource_rows(bidset, resource):
            is_price = label.endswith("$")
            decimals = price_decimals if is_price else mw_decimals
            prefix = price_prefix if is_price else ""
            shown = {he: v for he, v in values.items() if he in hours}
            cells = "".join(
                _fmt(None if col is None else shown.get(col), decimals=decimals, prefix=prefix)
                for col in plan
            )
            line = f"{label:<{_LABEL_WIDTH}}{cells}"
            if show_total:
                total_value = sum(shown.values()) if shown else None
                line += _fmt(total_value, decimals=decimals, prefix=prefix)
            lines.append(line)
    return "\n".join(lines)
