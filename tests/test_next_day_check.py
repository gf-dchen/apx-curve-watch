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
    monkeypatch.setattr(ndc.apx_bids, "fetch_bidset", lambda *a, **k: None)

    check = NextDayBidCheck((time(8, 0),))
    check.maybe_run(_config(), datetime(2026, 9, 13, 7, 59))
    assert calls == []


def test_check_fires_once_at_or_after_the_configured_time(monkeypatch):
    calls = []
    monkeypatch.setattr(ndc, "announce_missing_bids", lambda *a, **k: calls.append((a, k)))
    monkeypatch.setattr(ndc.apx_bids, "fetch_bidset", lambda *a, **k: None)

    check = NextDayBidCheck((time(8, 0),))
    check.maybe_run(_config(), datetime(2026, 9, 13, 8, 0))
    check.maybe_run(_config(), datetime(2026, 9, 13, 8, 5))  # same day, must not re-fire
    assert len(calls) == 1


def test_check_fires_again_the_next_day(monkeypatch):
    calls = []
    monkeypatch.setattr(ndc, "announce_missing_bids", lambda *a, **k: calls.append((a, k)))
    monkeypatch.setattr(ndc.apx_bids, "fetch_bidset", lambda *a, **k: None)

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

    monkeypatch.setattr(ndc.apx_bids, "fetch_bidset", fake_fetch)

    check = NextDayBidCheck((time(8, 0), time(8, 15), time(8, 30)))
    check.maybe_run(_config(), datetime(2026, 9, 13, 19, 13))
    assert len(fetch_calls) == 1
    assert len(announce_calls) == 1
    (check_label, *_rest), _kwargs = announce_calls[0]
    assert check_label == "08:30"  # the latest of the collapsed times, used as the label

    # None of the three should be able to fire again later that same day.
    check.maybe_run(_config(), datetime(2026, 9, 13, 20, 0))
    assert len(fetch_calls) == 1
