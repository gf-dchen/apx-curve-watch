from datetime import date

from gfem.foundry.bidding.apx_bids import BidSet, OfferCurve

from apx_curve_watch.curve_points import curve_points


def _bidset(*curves: OfferCurve) -> BidSet:
    return BidSet(fordate=date(2026, 9, 13), market_status="PRE", curves=list(curves))


def test_single_curve_points_are_returned_untouched_even_at_the_same_price():
    bidset = _bidset(OfferCurve("SAH_ESR1", 9, [(-200.0, 25.0), (0.0, 25.0)], "Slope", "Accepted"))
    assert curve_points(bidset, 9, "SAH_ESR1") == [(-200.0, 25.0), (0.0, 25.0)]


def test_no_curve_on_file_is_an_empty_list():
    bidset = _bidset()
    assert curve_points(bidset, 9, "NOBODY_HOME") == []


def test_two_curve_objects_fall_back_to_the_ladder_envelope():
    bidset = _bidset(
        OfferCurve("SAH_ESR1", 9, [(200.0, 50.0)], "Slope", "Accepted"),
        OfferCurve("SAH_ESR1", 9, [(200.0, 50.0)], "Slope", "Accepted"),
    )
    assert curve_points(bidset, 9, "SAH_ESR1") == [(200.0, 50.0)]
