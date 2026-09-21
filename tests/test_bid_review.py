from datetime import date

from gfem.foundry.bidding.apx_bids import BidSet, OfferCurve

from apx_curve_watch.bid_review import (
    check_charge_block,
    check_discharge_headroom,
    check_esr_symmetry,
    render_review,
    review,
    review_header,
)
from apx_curve_watch.day_book import DayBook

FORDATE = date(2026, 9, 21)
BOTH = ("SAH_ESR1", "SAH_ESR2")
BLOCK = (9, 10, 11, 12, 13)


def _book(curves=(), as_offers=None) -> DayBook:
    return DayBook(
        fordate=FORDATE,
        bidset=BidSet(fordate=FORDATE, market_status="PRE", curves=list(curves)),
        as_offers=as_offers or {},
    )


def _charge(resource: str, he: int, mw: float, price: float = 25.0) -> OfferCurve:
    """A charge bid as APX holds it: the 0-MW bookend plus the cumulative point."""
    return OfferCurve(resource, he, [(-mw, price), (0.0, price)], "Slope", "Accepted")


def _discharge(resource: str, he: int, mw: float, price: float = 65.0) -> OfferCurve:
    return OfferCurve(resource, he, [(0.0, price), (mw, price)], "Slope", "Accepted")


def _mirrored(maker, he: int, mw: float, **kw) -> list[OfferCurve]:
    return [maker(r, he, mw, **kw) for r in BOTH]


# --- rule 1: the HE09-13 charge block ---------------------------------------


def test_charge_block_passes_when_the_site_total_reaches_the_target():
    # HE09 -100, HE10 -200, HE11 -200 on each of two ESRs = 1000 MWh exactly.
    curves = _mirrored(_charge, 9, 100) + _mirrored(_charge, 10, 200) + _mirrored(_charge, 11, 200)
    assert check_charge_block(_book(curves), BOTH, BLOCK, 1000.0) is None


def test_charge_block_flags_a_shortfall_with_the_hour_by_hour_split():
    curves = _mirrored(_charge, 9, 100) + _mirrored(_charge, 10, 200)
    finding = check_charge_block(_book(curves), BOTH, BLOCK, 1000.0)
    assert finding is not None
    assert finding.kind == "charge-block"
    assert "600 MWh site-wide" in finding.headline
    assert "400 short of 1,000" in finding.headline
    assert "HE09 -200" in finding.lines[0]
    assert "HE12 0" in finding.lines[0]  # an hour with no charge bid reads as zero


def test_charge_block_counts_only_the_charge_side():
    curves = _mirrored(_charge, 9, 200) + _mirrored(_discharge, 10, 200)
    finding = check_charge_block(_book(curves), BOTH, BLOCK, 1000.0)
    assert finding is not None and "400 MWh site-wide" in finding.headline


def test_charge_block_is_disabled_by_an_empty_hour_list():
    assert check_charge_block(_book(), BOTH, (), 1000.0) is None


# --- rule 2: full discharge ladder wherever AS is also bid -------------------


def test_discharge_short_of_capacity_with_as_bid_is_flagged():
    book = _book(
        _mirrored(_discharge, 20, 100),
        {r: {20: {"ECRS": 100.0, "RRS-PFR": 100.0}} for r in BOTH},
    )
    finding = check_discharge_headroom(book, BOTH, 200.0)
    assert finding is not None
    assert finding.kind == "discharge-headroom"
    assert finding.lines[0] == "SAH_ESR1 HE20: tops out at 100 MW, with ECRS 100, RRS-PFR 100"
    assert len(finding.lines) == 2  # both ESRs


def test_a_full_200_mw_ladder_alongside_as_is_fine():
    book = _book(_mirrored(_discharge, 20, 200), {r: {20: {"ECRS": 100.0}} for r in BOTH})
    assert check_discharge_headroom(book, BOTH, 200.0) is None


def test_a_short_discharge_hour_without_as_is_left_alone():
    # No AS in the hour means nothing is stacked against the energy curve, so a
    # 100 MW offer is a real 100 MW offer rather than a capped-out one.
    assert check_discharge_headroom(_book(_mirrored(_discharge, 20, 100)), BOTH, 200.0) is None


def test_a_charge_hour_with_as_bid_is_not_a_discharge_shortfall():
    book = _book(_mirrored(_charge, 9, 100), {r: {9: {"ECRS": 100.0}} for r in BOTH})
    assert check_discharge_headroom(book, BOTH, 200.0) is None


# --- rule 3: the two ESRs mirror each other ---------------------------------


def test_identical_ladders_raise_nothing():
    assert check_esr_symmetry(_book(_mirrored(_charge, 9, 200)), BOTH) is None


def test_a_half_applied_edit_shows_both_sides():
    curves = [_charge("SAH_ESR1", 12, 90), _charge("SAH_ESR2", 12, 150)]
    finding = check_esr_symmetry(_book(curves), BOTH)
    assert finding is not None
    assert finding.kind == "esr-mismatch"
    assert finding.lines[0] == "HE12:"
    assert "SAH_ESR1: -90@$25.00, 0@$25.00" in finding.lines[1]
    assert "SAH_ESR2: -150@$25.00, 0@$25.00" in finding.lines[2]


def test_an_hour_one_esr_skipped_entirely_is_a_mismatch():
    finding = check_esr_symmetry(_book([_charge("SAH_ESR1", 12, 90)]), BOTH)
    assert finding is not None
    assert "SAH_ESR2: (nothing)" in finding.lines[2]


def test_symmetry_needs_two_resources_to_mean_anything():
    assert check_esr_symmetry(_book([_charge("SAH_ESR1", 12, 90)]), ("SAH_ESR1",)) is None


# --- the whole review -------------------------------------------------------


def _review(book, resources=BOTH, **overrides):
    kwargs = dict(
        charge_block_hours=BLOCK,
        charge_block_mwh=1000.0,
        min_discharge_mw=200.0,
        check_symmetry=True,
    )
    kwargs.update(overrides)
    return review(book, resources, **kwargs)


def test_a_book_that_looks_right_produces_no_findings():
    curves = (
        _mirrored(_charge, 9, 100)
        + _mirrored(_charge, 10, 200)
        + _mirrored(_charge, 11, 200)
        + _mirrored(_discharge, 20, 200)
    )
    book = _book(curves, {r: {20: {"ECRS": 100.0}} for r in BOTH})
    assert _review(book) == []


def test_every_failing_rule_is_reported_not_just_the_first():
    curves = [_charge("SAH_ESR1", 9, 100), _discharge("SAH_ESR1", 20, 100)]
    book = _book(curves, {"SAH_ESR1": {20: {"ECRS": 100.0}}})
    assert [f.kind for f in _review(book)] == [
        "charge-block",
        "discharge-headroom",
        "esr-mismatch",
    ]


def test_symmetry_can_be_switched_off():
    curves = [_charge("SAH_ESR1", 12, 90)]
    kinds = [f.kind for f in _review(_book(curves), check_symmetry=False)]
    assert "esr-mismatch" not in kinds


def test_resources_default_to_whatever_the_book_holds():
    curves = [_charge("SAH_ESR1", 12, 90)]
    findings = _review(_book(curves), resources=())
    assert [f.kind for f in findings] == ["charge-block"]  # one resource: no symmetry to check


def test_an_empty_book_is_left_to_the_missing_bids_nudge():
    assert _review(_book(), resources=()) == []


def test_render_indents_each_finding_under_its_headline():
    curves = [_charge("SAH_ESR1", 12, 90)]
    findings = _review(_book(curves), resources=("SAH_ESR1",))
    text = render_review(findings)
    assert text.splitlines()[0].startswith("charge HE09-HE13:")
    assert text.splitlines()[1].startswith("  HE09 0")
    assert "1 check failed" in review_header("08:30", FORDATE, findings)
    assert "2026-09-21 day-ahead bid looks wrong" in review_header("08:30", FORDATE, findings)
    # An off-schedule run (--review) has no wall clock to name.
    assert review_header("", FORDATE, findings).startswith("2026-09-21 day-ahead")
