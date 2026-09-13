from datetime import date

from gfem.foundry.bidding.apx_bids import BidSet, OfferCurve

from apx_curve_watch.snapshot import ladder_snapshot


def _bidset(*curves: OfferCurve) -> BidSet:
    return BidSet(fordate=date(2026, 9, 13), market_status="PRE", curves=list(curves))


def test_snapshot_defaults_to_every_resource_in_the_hour():
    bidset = _bidset(
        OfferCurve("SOHO_BESS1", 15, [(100.0, 20.0)], "Slope", "Accepted"),
        OfferCurve("RR_BESS1", 15, [(50.0, 30.0)], "Slope", "Accepted"),
        OfferCurve("SOHO_BESS1", 16, [(999.0, 999.0)], "Slope", "Accepted"),
    )
    snap = ladder_snapshot(bidset, 15)
    assert set(snap) == {"SOHO_BESS1", "RR_BESS1"}
    assert snap["SOHO_BESS1"] == [[100.0, 20.0]]


def test_snapshot_can_be_narrowed_to_named_resources():
    bidset = _bidset(
        OfferCurve("SOHO_BESS1", 15, [(100.0, 20.0)], "Slope", "Accepted"),
        OfferCurve("RR_BESS1", 15, [(50.0, 30.0)], "Slope", "Accepted"),
    )
    snap = ladder_snapshot(bidset, 15, resources=("SOHO_BESS1",))
    assert set(snap) == {"SOHO_BESS1"}


def test_snapshot_is_the_cumulative_envelope_not_a_raw_curve_dump():
    # Two curves for the same (resource, hour) -- e.g. a re-submission -- must not
    # sum: apx_bids.ladder takes the envelope, and the snapshot must preserve that.
    bidset = _bidset(
        OfferCurve("SOHO_BESS1", 15, [(200.0, 50.0)], "Slope", "Accepted"),
        OfferCurve("SOHO_BESS1", 15, [(200.0, 50.0)], "Slope", "Accepted"),
    )
    snap = ladder_snapshot(bidset, 15)
    assert snap["SOHO_BESS1"] == [[200.0, 50.0]]
