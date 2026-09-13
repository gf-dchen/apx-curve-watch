"""Render today's full-day energy ladder, HE by HE, as a plain-text table -- the
same HE01..HE24 layout as the APX MarketSuite bid-curve page.

Energy only: AS-Market products (ECRS etc., visible on the APX page but not
extracted by ``gfem``'s parser) are out of scope here -- see the handoff. Rows
are "Point N - MW" / "Point N - $" pairs, one pair per curve segment, exactly the
cumulative points ``apx_bids.ladder`` resolves (the envelope across duplicate
curves, same view the watcher diffs).
"""

from __future__ import annotations

from gfem.foundry.bidding import apx_bids

ALL_HOURS = tuple(range(1, 25))
_LABEL_WIDTH = 14
_COL_WIDTH = 9


def resource_rows(bidset: apx_bids.BidSet, resource: str) -> list[tuple[str, dict[int, float]]]:
    """``[(row_label, {he: value})]`` for one resource's energy ladder across the day."""
    ladders = {he: apx_bids.ladder(bidset, he, resource=resource) for he in ALL_HOURS}
    max_points = max((len(pts) for pts in ladders.values()), default=0)

    rows: list[tuple[str, dict[int, float]]] = []
    for i in range(max_points):
        mw_row = {he: pts[i][0] for he, pts in ladders.items() if i < len(pts)}
        price_row = {he: pts[i][1] for he, pts in ladders.items() if i < len(pts)}
        rows.append((f"Point {i + 1} - MW", mw_row))
        rows.append((f"Point {i + 1} - $", price_row))
    return rows


def _fmt(value: float | None) -> str:
    return f"{value:>{_COL_WIDTH}.2f}" if value is not None else " " * _COL_WIDTH


def render_table(bidset: apx_bids.BidSet, resources: tuple[str, ...] = ()) -> str:
    names = resources or tuple(bidset.resources)
    header = "".join(f"HE{h:02d}".rjust(_COL_WIDTH) for h in ALL_HOURS) + "Total".rjust(_COL_WIDTH)
    lines = [" " * _LABEL_WIDTH + header]
    for resource in names:
        lines.append(resource)
        for label, values in resource_rows(bidset, resource):
            cells = "".join(_fmt(values.get(he)) for he in ALL_HOURS)
            total = _fmt(sum(values.values())) if values else _fmt(None)
            lines.append(f"{label:<{_LABEL_WIDTH}}{cells}{total}")
    return "\n".join(lines)
