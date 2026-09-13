from datetime import date

from gfem.foundry.bidding.apx_bids import BidSet, OfferCurve

from apx_curve_watch.table import ALL_HOURS, render_table, resource_rows


def _bidset(*curves: OfferCurve) -> BidSet:
    return BidSet(fordate=date(2026, 9, 13), market_status="PRE", curves=list(curves))


def test_resource_rows_pairs_mw_and_price_per_segment():
    bidset = _bidset(
        OfferCurve("SAH_ESR1", 9, [(-200.0, 25.0)], "Slope", "Accepted"),
        OfferCurve("SAH_ESR1", 10, [(-200.0, 25.0), (0.0, 30.0)], "Slope", "Accepted"),
    )
    rows = resource_rows(bidset, "SAH_ESR1")
    labels = [label for label, _ in rows]
    assert labels == ["Point 1 - MW", "Point 1 - $", "Point 2 - MW", "Point 2 - $"]
    point1_mw = dict(rows)["Point 1 - MW"]
    assert point1_mw == {9: -200.0, 10: -200.0}
    point2_mw = dict(rows)["Point 2 - MW"]
    assert point2_mw == {10: 0.0}  # HE9 had no second segment -- absent, not zero


def test_resource_with_no_curves_at_all_has_no_rows():
    bidset = _bidset()
    assert resource_rows(bidset, "NOBODY_HOME") == []


def test_render_table_includes_every_hour_column_and_a_total():
    bidset = _bidset(OfferCurve("SAH_ESR1", 9, [(-200.0, 25.0)], "Slope", "Accepted"))
    table = render_table(bidset)
    header = table.splitlines()[0]
    assert all(f"HE{h:02d}" in header for h in ALL_HOURS)
    assert "Total" in header
    point1_mw_row = next(line for line in table.splitlines() if line.startswith("Point 1 - MW"))
    assert point1_mw_row.rstrip().endswith("-200.00")  # only segment this hour -> total = itself


def test_render_table_can_be_narrowed_to_named_resources():
    bidset = _bidset(
        OfferCurve("SAH_ESR1", 9, [(-200.0, 25.0)], "Slope", "Accepted"),
        OfferCurve("SAH_ESR2", 9, [(-100.0, 25.0)], "Slope", "Accepted"),
    )
    table = render_table(bidset, resources=("SAH_ESR1",))
    assert "SAH_ESR1" in table
    assert "SAH_ESR2" not in table
