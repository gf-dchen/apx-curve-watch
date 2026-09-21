from datetime import date, datetime, time

from gfem.foundry.bidding.apx_bids import BidSet, OfferCurve

from apx_curve_watch import next_day_check as ndc
from apx_curve_watch.config import WatchConfig
from apx_curve_watch.next_day_check import NextDayBidCheck, missing_resources


def _config(**overrides) -> WatchConfig:
    base = dict(
        participant="QGFEN",
        env="prod",
        resources=(),
        poll_seconds=30,
        storage_dir="./curves",
        teams_webhook_url=None,
        next_day_check_times=(time(8, 0), time(8, 15)),
        log_file="",
    )
    base.update(overrides)
    return WatchConfig(**base)


def _bidset(*curves: OfferCurve) -> BidSet:
    return BidSet(fordate=date(2026, 9, 14), market_status="PRE", curves=list(curves))


def test_missing_resources_flags_entire_book_when_nothing_configured():
    assert missing_resources(None, ()) == ("(entire book)",)
    assert missing_resources(_bidset(), ()) == ("(entire book)",)


def test_missing_resources_is_empty_when_book_has_anything_and_none_configured():
    bidset = _bidset(OfferCurve("SAH_ESR1", 9, [(-200.0, 25.0)], "Slope", "Accepted"))
    assert missing_resources(bidset, ()) == ()


def test_missing_resources_names_the_specific_gap():
    bidset = _bidset(OfferCurve("SAH_ESR1", 9, [(-200.0, 25.0)], "Slope", "Accepted"))
    assert missing_resources(bidset, ("SAH_ESR1", "SAH_ESR2")) == ("SAH_ESR2",)


def test_missing_resources_all_missing_when_bidset_is_none():
    assert missing_resources(None, ("SAH_ESR1", "SAH_ESR2")) == ("SAH_ESR1", "SAH_ESR2")


def test_check_does_not_fire_before_the_configured_time(monkeypatch):
    calls = []
    monkeypatch.setattr(ndc, "announce_missing_bids", lambda *a, **k: calls.append((a, k)))
    monkeypatch.setattr(ndc, "fetch_day_book", lambda *a, **k: None)

    check = NextDayBidCheck((time(8, 0),))
    check.maybe_run(_config(), datetime(2026, 9, 13, 7, 59))
    assert calls == []


def test_check_fires_once_at_or_after_the_configured_time(monkeypatch):
    calls = []
    monkeypatch.setattr(ndc, "announce_missing_bids", lambda *a, **k: calls.append((a, k)))
    monkeypatch.setattr(ndc, "fetch_day_book", lambda *a, **k: None)

    check = NextDayBidCheck((time(8, 0),))
    check.maybe_run(_config(), datetime(2026, 9, 13, 8, 0))
    check.maybe_run(_config(), datetime(2026, 9, 13, 8, 5))  # same day, must not re-fire
    assert len(calls) == 1


def test_check_fires_again_the_next_day(monkeypatch):
    calls = []
    monkeypatch.setattr(ndc, "announce_missing_bids", lambda *a, **k: calls.append((a, k)))
    monkeypatch.setattr(ndc, "fetch_day_book", lambda *a, **k: None)

    check = NextDayBidCheck((time(8, 0),))
    check.maybe_run(_config(), datetime(2026, 9, 13, 8, 0))
    check.maybe_run(_config(), datetime(2026, 9, 14, 8, 0))
    assert len(calls) == 2


def test_a_late_start_collapses_every_already_passed_time_into_one_check(monkeypatch):
    # Starting the process at 19:13 -- well past all 12 default check times --
    # must not fire one fetch/announcement per already-passed time.
    fetch_calls = []
    announce_calls = []
    monkeypatch.setattr(ndc, "announce_missing_bids", lambda *a, **k: announce_calls.append((a, k)))

    def fake_fetch(*args, **kwargs):
        fetch_calls.append((args, kwargs))
        return None

    monkeypatch.setattr(ndc, "fetch_day_book", fake_fetch)

    check = NextDayBidCheck((time(8, 0), time(8, 15), time(8, 30)))
    check.maybe_run(_config(), datetime(2026, 9, 13, 19, 13))
    assert len(fetch_calls) == 1
    assert len(announce_calls) == 1
    (check_label, *_rest), _kwargs = announce_calls[0]
    assert check_label == "08:30"  # the latest of the collapsed times, used as the label

    # None of the three should be able to fire again later that same day.
    check.maybe_run(_config(), datetime(2026, 9, 13, 20, 0))
    assert len(fetch_calls) == 1


def _day_book(curves=(), as_offers=None):
    from apx_curve_watch.day_book import DayBook

    return DayBook(
        fordate=date(2026, 9, 14),
        bidset=BidSet(fordate=date(2026, 9, 14), market_status="PRE", curves=list(curves)),
        as_offers=as_offers or {},
    )


def _wire(monkeypatch, book):
    """Patch the fetch + both announcements; return the two call logs."""
    missing_calls, review_calls = [], []
    monkeypatch.setattr(ndc, "fetch_day_book", lambda *a, **k: book)
    monkeypatch.setattr(ndc, "announce_missing_bids", lambda *a, **k: missing_calls.append(a))
    monkeypatch.setattr(ndc, "announce_bid_review", lambda *a, **k: review_calls.append(a))
    return missing_calls, review_calls


def test_a_book_on_file_is_reviewed_against_the_desk_rules(monkeypatch):
    # 100 MW of discharge in an hour that also bids ECRS -- rule 2's case.
    book = _day_book(
        [OfferCurve("SAH_ESR1", 20, [(0.0, 65.0), (100.0, 65.0)], "Slope", "Accepted")],
        {"SAH_ESR1": {20: {"ECRS": 100.0}}},
    )
    _missing, review_calls = _wire(monkeypatch, book)

    NextDayBidCheck((time(8, 0),)).maybe_run(_config(), datetime(2026, 9, 13, 8, 0))

    assert len(review_calls) == 1
    check_label, fordate, findings = review_calls[0]
    assert (check_label, fordate) == ("08:00", date(2026, 9, 14))
    assert "discharge-headroom" in [f.kind for f in findings]


def test_a_book_that_passes_every_rule_reports_nothing(monkeypatch):
    curves = [
        OfferCurve(r, he, [(-mw, 25.0), (0.0, 25.0)], "Slope", "Accepted")
        for r in ("SAH_ESR1", "SAH_ESR2")
        for he, mw in ((9, 100.0), (10, 200.0), (11, 200.0))
    ] + [
        # ...and the day has to sell somewhere, or rule 3 fires.
        OfferCurve(r, 20, [(0.0, 65.0), (200.0, 65.0)], "Slope", "Accepted")
        for r in ("SAH_ESR1", "SAH_ESR2")
    ]
    as_offers = {r: {20: {"ECRS": 100.0}} for r in ("SAH_ESR1", "SAH_ESR2")}
    _missing, review_calls = _wire(monkeypatch, _day_book(curves, as_offers))

    NextDayBidCheck((time(8, 0),)).maybe_run(
        _config(resources=("SAH_ESR1", "SAH_ESR2")), datetime(2026, 9, 13, 8, 0)
    )

    assert review_calls[0][2] == []


def test_a_failed_fetch_is_not_reviewed(monkeypatch):
    missing_calls, review_calls = _wire(monkeypatch, None)

    NextDayBidCheck((time(8, 0),)).maybe_run(_config(), datetime(2026, 9, 13, 8, 0))

    assert len(missing_calls) == 1  # the nudge still goes out
    assert review_calls == []


def test_a_resource_with_nothing_on_file_is_nudged_not_reviewed(monkeypatch):
    # An absent ESR would otherwise fail the symmetry rule in all 24 hours, on
    # top of the nudge that already says the book isn't there.
    book = _day_book([OfferCurve("SAH_ESR1", 9, [(-200.0, 25.0)], "Slope", "Accepted")])
    missing_calls, review_calls = _wire(monkeypatch, book)

    NextDayBidCheck((time(8, 0),)).maybe_run(
        _config(resources=("SAH_ESR1", "SAH_ESR2")), datetime(2026, 9, 13, 8, 0)
    )

    assert missing_calls[0][2] == ("SAH_ESR2",)
    assert review_calls == []
