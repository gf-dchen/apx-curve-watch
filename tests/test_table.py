from datetime import date

from gfem.foundry.bidding.apx_bids import BidSet, OfferCurve

from apx_curve_watch.table import render_table, resource_rows


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


def test_resource_rows_keeps_both_points_when_they_share_a_price():
    # A flat/vertical segment -- e.g. real SAH_ESR1 data: [(-200, 25), (0, 25)] --
    # must not be mistaken for a duplicate curve at that price.
    bidset = _bidset(
        OfferCurve("SAH_ESR1", 9, [(-200.0, 25.0), (0.0, 25.0)], "Slope", "Accepted"),
    )
    rows = resource_rows(bidset, "SAH_ESR1")
    labels = [label for label, _ in rows]
    assert labels == ["Point 1 - MW", "Point 1 - $", "Point 2 - MW", "Point 2 - $"]
    assert dict(rows)["Point 1 - MW"] == {9: -200.0}
    assert dict(rows)["Point 2 - MW"] == {9: 0.0}


def test_resource_with_no_curves_at_all_has_no_rows():
    bidset = _bidset()
    assert resource_rows(bidset, "NOBODY_HOME") == []


def test_render_table_collapses_a_long_run_of_empty_hours_into_one_ellipsis_column():
    bidset = _bidset(OfferCurve("SAH_ESR1", 9, [(-200.0, 25.0)], "Slope", "Accepted"))
    table = render_table(bidset)
    header = table.splitlines()[0]
    assert "HE09" in header
    assert "HE08" not in header  # collapsed into the leading "..." run
    assert "HE10" not in header  # collapsed into the trailing "..." run
    assert "..." in header
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


def test_render_table_can_be_narrowed_to_a_range_of_hours():
    bidset = _bidset(
        OfferCurve("SAH_ESR1", 9, [(-200.0, 25.0)], "Slope", "Accepted"),
        OfferCurve("SAH_ESR1", 16, [(150.0, 50.0)], "Slope", "Accepted"),
    )
    table = render_table(bidset, hours=tuple(range(16, 25)))
    header = table.splitlines()[0]
    assert "HE09" not in header  # outside the requested window entirely
    assert "HE16" in header
    point1_mw_row = next(line for line in table.splitlines() if line.startswith("Point 1 - MW"))
    assert point1_mw_row.rstrip().endswith("150.00")  # total only over the shown hours, not HE09


def test_a_gap_between_two_populated_hours_collapses_to_one_ellipsis():
    bidset = _bidset(
        OfferCurve("SAH_ESR1", 13, [(0.0, 30.0)], "Slope", "Accepted"),
        OfferCurve("SAH_ESR1", 16, [(1.0, -250.0)], "Slope", "Accepted"),
    )
    table = render_table(bidset, hours=tuple(range(13, 17)))
    header = table.splitlines()[0]
    assert "HE13" in header
    assert "HE16" in header
    assert "HE14" not in header
    assert "HE15" not in header
    assert header.count("...") == 1  # one placeholder for the HE14-15 gap, not two blanks


def test_a_resource_with_nothing_in_the_shown_window_is_left_out_entirely():
    bidset = _bidset(
        OfferCurve("SAH_ESR1", 9, [(-200.0, 25.0)], "Slope", "Accepted"),
        OfferCurve(
            "SAH_ESR2", 20, [(150.0, 50.0)], "Slope", "Accepted"
        ),  # outside the window below
    )
    table = render_table(bidset, hours=(9,))
    assert "SAH_ESR1" in table
    assert "SAH_ESR2" not in table  # nothing on file at HE9, so omitted, not an all-blank section


def test_when_every_shown_resource_is_empty_only_the_header_remains():
    bidset = _bidset(OfferCurve("SAH_ESR1", 20, [(150.0, 50.0)], "Slope", "Accepted"))
    table = render_table(bidset, hours=(9,))
    assert "SAH_ESR1" not in table


def test_show_total_false_drops_the_total_column_and_its_header():
    bidset = _bidset(OfferCurve("SAH_ESR1", 9, [(-200.0, 25.0)], "Slope", "Accepted"))
    table = render_table(bidset, show_total=False)
    assert "Total" not in table
    point1_mw_row = next(line for line in table.splitlines() if line.startswith("Point 1 - MW"))
    assert point1_mw_row.rstrip().endswith("-200.00")  # nothing trailing after the last hour cell


def test_mw_decimals_rounds_mw_but_leaves_price_alone():
    bidset = _bidset(OfferCurve("SAH_ESR1", 9, [(-200.4, 25.4)], "Slope", "Accepted"))
    table = render_table(bidset, mw_decimals=0)
    mw_row = next(line for line in table.splitlines() if line.startswith("Point 1 - MW"))
    price_row = next(line for line in table.splitlines() if line.startswith("Point 1 - $"))
    assert "-200.4" not in mw_row
    assert "-200" in mw_row
    assert "25.40" in price_row  # price_decimals still defaults to 2


def test_price_prefix_is_applied_only_to_price_rows():
    bidset = _bidset(OfferCurve("SAH_ESR1", 9, [(-200.0, 25.0)], "Slope", "Accepted"))
    table = render_table(bidset, price_prefix="$")
    mw_row = next(line for line in table.splitlines() if line.startswith("Point 1 - MW"))
    price_row = next(line for line in table.splitlines() if line.startswith("Point 1 - $"))
    assert "$" not in mw_row
    assert "$25.00" in price_row


def test_teams_style_formatting_combines_all_three_options():
    bidset = _bidset(OfferCurve("SAH_ESR1", 9, [(-200.4, 25.0)], "Slope", "Accepted"))
    table = render_table(bidset, show_total=False, mw_decimals=0, price_prefix="$")
    assert "Total" not in table
    mw_row = next(line for line in table.splitlines() if line.startswith("Point 1 - MW"))
    price_row = next(line for line in table.splitlines() if line.startswith("Point 1 - $"))
    assert mw_row.rstrip().endswith("-200")
    assert price_row.rstrip().endswith("$25.00")
